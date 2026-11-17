"""Normalized coding distributions; reversible on explicit unit sequences."""
from collections import Counter, defaultdict
import itertools
import math

BOS = '<BOS>'
EOS = '<EOS>'
UNK = '<UNK>'
NONE = '<NONE>'
G = frozenset('ktpf')
POSITIONS = ('paragraph_first', 'line_first', 'other')


def universe(representation='eva'):
    result = set("abcdefghijklmnopqrstuvwxyz'")
    result.update('@%03d;' % i for i in range(1000))
    if representation == 'merged':
        result.update(('ch', 'sh', 'cth', 'ckh', 'cph', 'cfh'))
    return frozenset(result)


def logmix(a, b, weight):
    if weight == 0:
        return a
    if weight == 1:
        return b
    x = math.log2(1-weight) + a
    y = math.log2(weight) + b
    m = max(x, y)
    return m + math.log2(2**(x-m) + 2**(y-m))


class BodyLM:
    def __init__(self, words, alphabet, omega, order=4, alpha=5):
        self.alphabet = frozenset(alphabet)
        self.omega = frozenset(omega)
        assert self.alphabet <= self.omega
        self.unseen = self.omega-self.alphabet
        self.escape_size = len(self.unseen)
        self.order, self.alpha = order, alpha
        self.vocab = tuple(sorted(self.alphabet | {EOS} | ({UNK} if self.unseen else set())))
        self.counts = defaultdict(Counter)
        self.totals = Counter()
        self.prob_cache, self.log_cache = {}, {}
        self.training_words = len(words)
        for word in words:
            assert word and set(word) <= self.alphabet
            history = self.initial_history
            for c in tuple(word)+(EOS,):
                for n in range(order):
                    h = history[-n:] if n else ()
                    self.counts[h][c] += 1
                    self.totals[h] += 1
                history = self.advance(history, c)

    @property
    def initial_history(self):
        return (BOS,)*(self.order-1)

    def advance(self, h, c):
        return (h+(c,))[-(self.order-1):] if self.order > 1 else ()

    def mapped(self, c):
        assert c in self.omega, ('out of frozen universe', c)
        return c if c in self.alphabet else UNK

    def prob(self, h, c):
        assert c in self.vocab
        key = (h, c)
        if key in self.prob_cache:
            return self.prob_cache[key]
        lower = self.prob(h[1:], c) if h else 1/len(self.vocab)
        p = (self.counts.get(h, {}).get(c, 0)+self.alpha*lower)/(self.totals.get(h, 0)+self.alpha)
        self.prob_cache[key] = p
        return p

    def actual_prob(self, h, c):
        mapped = self.mapped(c)
        return self.prob(h, mapped)/(self.escape_size if mapped == UNK else 1)

    @property
    def empty_prob(self):
        return self.prob(self.initial_history, EOS)

    @property
    def nonempty_mass(self):
        return 1-self.empty_prob

    def logp_raw(self, word):
        word = tuple(word)
        if word in self.log_cache:
            return self.log_cache[word]
        history = self.initial_history
        result = 0.0
        for c in word:
            mapped = self.mapped(c)
            result += math.log2(self.prob(history, mapped))
            if mapped == UNK:
                result -= math.log2(self.escape_size)
            history = self.advance(history, mapped)
        result += math.log2(self.prob(history, EOS))
        self.log_cache[word] = result
        return result

    def logp_full(self, word):
        assert word
        return self.logp_raw(word)-math.log2(self.nonempty_mass)

    def first_prior(self):
        return {c: self.actual_prob(self.initial_history, c)/self.nonempty_mass for c in sorted(self.omega)}

    def payload(self):
        histories = sorted(self.counts, key=lambda x: (len(x), x))
        rows = []
        max_error = 0.0
        for h in histories:
            probs = [self.prob(h, c) for c in self.vocab]
            max_error = max(max_error, abs(sum(probs)-1))
            rows.append(dict(history=list(h), total=self.totals[h],
                counts=[self.counts[h][c] for c in self.vocab], probabilities=probs))
        max_total = max(self.totals.values(), default=0)
        epsilon = (self.alpha/(max_total+self.alpha))**self.order/len(self.vocab)
        return dict(order=self.order, alpha=self.alpha, alphabet=sorted(self.alphabet),
            omega=sorted(self.omega), vocab=list(self.vocab), escape_size=self.escape_size,
            training_words=self.training_words, empty_probability=self.empty_prob,
            first_actual_unit_prior=self.first_prior(), contexts=rows,
            conditional_sum_max_error=max_error, eos_uniform_lower_bound=epsilon,
            termination_proof='Finite mapped contexts; every transition has EOS probability at least epsilon>0. Probability of surviving n more units <= (1-epsilon)^n, hence eventual termination probability is one.',
            unseen_context_rule='Zero counts and zero total, recursively back off to suffix. Empty history backs off to uniform over vocab.',
            escape_rule='Each UNK emission is split uniformly across omega minus alphabet; update history using UNK while retaining the emitted identity.')

    @classmethod
    def from_payload(cls, payload):
        result = cls.__new__(cls)
        result.alphabet, result.omega = frozenset(payload['alphabet']), frozenset(payload['omega'])
        result.unseen = result.omega-result.alphabet
        result.escape_size = len(result.unseen)
        result.order, result.alpha = payload['order'], payload['alpha']
        result.vocab = tuple(payload['vocab'])
        result.training_words = payload['training_words']
        result.counts, result.totals = defaultdict(Counter), Counter()
        for row in payload['contexts']:
            h = tuple(row['history'])
            result.counts[h] = Counter({c: n for c, n in zip(result.vocab, row['counts']) if n})
            result.totals[h] = row['total']
        result.prob_cache, result.log_cache = {}, {}
        return result


class PrefixFactor:
    def __init__(self, body, training_records, beta, kind):
        assert kind in ('gallows', 'any_first')
        self.body, self.beta, self.kind = body, beta, kind
        first = body.first_prior()
        if kind == 'gallows':
            prior = {g: first.get(g, 0) for g in sorted(G)}
            prior[NONE] = sum(p for c, p in first.items() if c not in G)
            self.z_none = sum(body.actual_prob(body.initial_history, c) for c in body.omega if c not in G)
            assert self.z_none > 0
        else:
            prior = first
            self.z_none = None
        self.prior = prior
        self.tables, self.counts, self.ns = {}, {}, {}
        for position in POSITIONS:
            counts = Counter()
            for r in training_records:
                if r['position'] == position and r['word']:
                    c = r['word'][0]
                    counts[c if kind == 'any_first' or c in G else NONE] += 1
            n = sum(counts.values())
            self.counts[position] = counts
            self.ns[position] = n
            self.tables[position] = {c: (counts[c]+beta*p)/(n+beta) for c, p in prior.items()}

    def decompose(self, word):
        assert word
        c = word[0]
        if self.kind == 'any_first' or c in G:
            return c, tuple(word[1:])
        return NONE, tuple(word)

    def reconstruct(self, prefix, root):
        if self.kind == 'gallows' and prefix == NONE:
            assert root and root[0] not in G
            return tuple(root)
        assert prefix in (G if self.kind == 'gallows' else self.body.omega)
        return (prefix,)+tuple(root)

    def cost(self, word, position='paragraph_first'):
        prefix, root = self.decompose(word)
        assert self.reconstruct(prefix, root) == tuple(word)
        prefix_bits = -math.log2(self.tables[position][prefix])
        body_bits = -self.body.logp_raw(root)
        normalization_bits = math.log2(self.z_none) if prefix == NONE else 0.0
        return dict(prefix=prefix, root=list(root), prefix_bits=prefix_bits,
            body_raw_bits=body_bits, support_normalization_bits=normalization_bits,
            total_bits=prefix_bits+body_bits+normalization_bits,
            root_escape_count=sum(c not in self.body.alphabet for c in root),
            root_escape_bits=sum(c not in self.body.alphabet for c in root)*math.log2(self.body.escape_size) if self.body.escape_size else 0.0,
            prefix_is_escaped=prefix != NONE and prefix not in self.body.alphabet)

    def logp(self, word, position='paragraph_first'):
        return -self.cost(word, position)['total_bits']

    def payload(self):
        return dict(kind=self.kind, beta=self.beta, prior=self.prior, z_none=self.z_none,
            training_counts={p: dict(c) for p, c in self.counts.items()}, training_totals=self.ns,
            prefix_probabilities=self.tables,
            probability_sum_error={p: abs(sum(v.values())-1) for p, v in self.tables.items()},
            main_scope='Only paragraph_first is replaced by the factor. Other positions use the same complete-word body baseline. All three prefix tables are retained for audit.')

    @classmethod
    def from_payload(cls, body, payload):
        result = cls.__new__(cls)
        result.body, result.kind, result.beta = body, payload['kind'], payload['beta']
        result.prior, result.z_none = payload['prior'], payload['z_none']
        result.tables, result.counts, result.ns = payload['prefix_probabilities'], payload['training_counts'], payload['training_totals']
        return result


def verify_models():
    # A deliberately unseen unit b exercises both the first-unit escape and
    # the NONE branch; k-only exercises an empty root.
    omega = frozenset(('a', 'b', 'k'))
    words = [tuple('a'), tuple('ka'), tuple('aa'), tuple('ak'), tuple('k')]
    records = [dict(word=w, position=POSITIONS[i % 3]) for i, w in enumerate(words)]
    all_reports = []
    for order in (1, 2, 3, 4):
        body = BodyLM(words, {'a', 'k'}, omega, order=order, alpha=5)
        for h in [(), body.initial_history, ('a',), ('a', 'k'), (UNK,)*3]:
            assert abs(sum(body.prob(h, c) for c in body.vocab)-1) < 1e-12
            expanded = sum(body.actual_prob(h, c) for c in omega)+body.prob(h, EOS)
            assert abs(expanded-1) < 1e-12
        all_words = [w for n in range(1, 7) for w in itertools.product(sorted(omega), repeat=n)]
        short_words = [w for w in all_words if len(w) <= 5]
        root_mass = sum(2**body.logp_raw(w) for w in [()]+short_words)
        raw_mass = sum(2**body.logp_raw(w) for w in all_words)
        full_sum = sum(2**body.logp_full(w) for w in all_words)
        assert abs(full_sum-raw_mass/body.nonempty_mass) < 1e-11
        for kind in ('gallows', 'any_first'):
            factor = PrefixFactor(body, records, 5, kind)
            for probs in factor.tables.values():
                assert abs(sum(probs.values())-1) < 1e-12
            observed = sum(2**factor.logp(w) for w in all_words)
            if kind == 'any_first':
                expected = root_mass
            else:
                non_g_mass = sum(2**body.logp_raw(w) for w in all_words if w[0] not in G)
                pg = sum(p for c, p in factor.tables['paragraph_first'].items() if c in G)
                expected = pg*root_mass+factor.tables['paragraph_first'][NONE]*non_g_mass/factor.z_none
            assert abs(observed-expected) < 1e-11, (order, kind, observed, expected)
            for w in all_words:
                c = factor.cost(w)
                assert abs(c['total_bits']+factor.logp(w)) < 1e-12
                assert factor.reconstruct(c['prefix'], c['root']) == w
                if kind == 'gallows':
                    assert (c['prefix'] == NONE) == (w[0] not in G)
            if kind == 'gallows':
                assert factor.cost(('k',))['root'] == []
                assert factor.cost(('b',))['prefix'] == NONE
            else:
                assert factor.cost(('b',))['prefix_is_escaped'] is True
            all_reports.append(dict(order=order, kind=kind, enumerated_nonempty_words=len(all_words),
                max_length=6, truncated_mass=observed, analytic_truncated_mass=expected,
                discrepancy=abs(observed-expected)))
    return dict(toy_enumeration=all_reports, conditional_normalization=True,
        escape_expansion_normalizes=True, none_and_gallows_disjoint=True,
        single_unit_empty_root=True, unknown_first_unit=True, reversible_unit_sequence=True)
