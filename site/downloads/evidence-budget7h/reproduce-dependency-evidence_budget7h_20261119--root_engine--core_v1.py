"""Conditional information fibres on whole signatures. No file access or image inference."""
import numpy as np

IDS = ('F01', 'F02', 'F03', 'F04', 'F05', 'F06')
TARGETS = ('H', 'H4', 'H_minus_H4')
CLASS_NAMES = ('CONFLICT', 'NONE_JOINT_POSITIVE', 'MIXED', 'ALL_JOINT_POSITIVE')
ROW_FIELDS = ('class', 'unique_count', 'tagged_count', 'positive_unique_count',
              'positive_tagged_count', 'compatible_g_bits',
              'H_min32', 'H_max32', 'H4_min32', 'H4_max32',
              'difference_min32', 'difference_max32',
              'H_min_witness', 'H_max_witness', 'H4_min_witness', 'H4_max_witness',
              'difference_min_witness', 'difference_max_witness',
              'positive_witness', 'nonpositive_witness')


def joint_flags(h, h4, valid):
    return (h > 0) & (h4 > 0) & valid


def normalize(states):
    if not states or len({s['id'] for s in states}) != len(states):
        raise ValueError('Nonempty unique global state IDs required')
    if len(states) > 30:
        raise ValueError('At most30 explicitly tagged states supported')
    out = []
    for state in states:
        if set(state['entries']) != set(IDS):
            raise ValueError('All six entries required in every state')
        entries = {}
        for eid in IDS:
            raw = state['entries'][eid]
            if not raw or any(len(v) != 4 or any(type(x) is not int or x not in (0,1,2) for x in v) for v in raw):
                raise ValueError('Nonempty domain of complete four-integer capped signatures required')
            entries[eid] = sorted(set(map(tuple, raw)))
        out.append({'id': state['id'], 'entries': entries})
    return out


def build_tensor(states, factor_f02=False):
    states = normalize(states)
    alphabet = {eid: sorted(set().union(*(set(s['entries'][eid]) for s in states))) for eid in IDS}
    if factor_f02 and any(s['entries']['F02'] != states[0]['entries']['F02'] for s in states):
        raise ValueError('F02 factorization requires identical domains in every shared state')
    core = tuple(eid for eid in IDS if not (factor_f02 and eid == 'F02'))
    shape = tuple(len(alphabet[eid]) for eid in core)
    coordinates = {}
    for axis, eid in enumerate(core):
        dimensions = [1] * len(core) + [4]
        dimensions[axis] = shape[axis]
        coordinates[eid] = np.asarray(alphabet[eid], dtype=np.int16).reshape(dimensions)
    def distance(a,b):
        return np.abs(coordinates[a] - coordinates[b]).sum(axis=-1, dtype=np.int16)
    d34, d56 = distance('F03','F04'), distance('F05','F06')
    d14, d16 = distance('F01','F04'), distance('F01','F06')
    d36, d45 = distance('F03','F06'), distance('F04','F05')
    h = np.broadcast_to(d14+d16+d36+d45-2*d34-2*d56, shape).copy()
    h4 = np.broadcast_to(2*(d36+d45-d34-d56), shape).copy()
    masks = []
    for state in states:
        mask = np.ones(shape, dtype=bool)
        for axis, eid in enumerate(core):
            allowed = set(state['entries'][eid])
            dimensions = [1] * len(core)
            dimensions[axis] = shape[axis]
            mask &= np.asarray([v in allowed for v in alphabet[eid]], dtype=bool).reshape(dimensions)
        masks.append(mask)
    return {'states':states, 'alphabet':alphabet, 'core':core, 'shape':shape,
            'factor_f02':factor_f02, 'scores':(h,h4,h-h4), 'g_masks':masks}


def table(model, observed, regime='unknown'):
    """Canonical table. F02 count factors are applied by the logical subset decoder."""
    observed = tuple(observed)
    if observed != tuple(e for e in model['core'] if e in observed) or len(set(observed)) != len(observed):
        raise ValueError('Observed IDs must be a sorted subset of canonical core IDs')
    labels = [s['id'] for s in model['states']]
    if regime != 'unknown' and regime not in labels:
        raise ValueError('Unknown regime')
    active = list(range(len(labels))) if regime == 'unknown' else [labels.index(regime)]
    obs_axes = [model['core'].index(eid) for eid in observed]
    other_axes = [i for i in range(len(model['core'])) if i not in obs_axes]
    order = obs_axes + other_axes
    n_rows = int(np.prod([model['shape'][i] for i in obs_axes], dtype=np.int64))
    n_remaining = int(np.prod([model['shape'][i] for i in other_axes], dtype=np.int64))
    def matrix(x):
        return np.transpose(x, order).reshape(n_rows, n_remaining)
    per_g = [matrix(model['g_masks'][i]) for i in active]
    tagged = np.sum(per_g, axis=0, dtype=np.int64)
    valid = tagged > 0
    values = [matrix(v) for v in model['scores']]
    positive = joint_flags(values[0], values[1], valid)
    n_unique = valid.sum(axis=1, dtype=np.int64)
    n_tagged = tagged.sum(axis=1, dtype=np.int64)
    n_positive = positive.sum(axis=1, dtype=np.int64)
    n_positive_tagged = (tagged * positive).sum(axis=1, dtype=np.int64)
    classes = np.where(n_unique == 0, 0, np.where(n_positive == 0, 1, np.where(n_positive == n_unique, 3, 2)))
    bits = np.zeros(n_rows, dtype=np.int64)
    for i, mask in zip(active, per_g):
        bits |= (mask.any(axis=1).astype(np.int64) << i)
    flat_ids = matrix(np.arange(int(np.prod(model['shape'])), dtype=np.int64).reshape(model['shape']))
    rows = np.arange(n_rows)
    bounds, witnesses = [], []
    for value in values:
        for upper in (False, True):
            masked = np.where(valid, value, -32767 if upper else 32767)
            arg = masked.argmax(axis=1) if upper else masked.argmin(axis=1)
            bounds.append(masked[rows, arg])
            witnesses.append(flat_ids[rows, arg])
    yes_arg = positive.argmax(axis=1)
    no_mask = valid & ~positive
    no_arg = no_mask.argmax(axis=1)
    columns = [classes,n_unique,n_tagged,n_positive,n_positive_tagged,bits,*bounds,*witnesses,
               flat_ids[rows,yes_arg],flat_ids[rows,no_arg]]
    packed = np.stack(columns, axis=1).tolist()
    for index, row in enumerate(packed):
        if n_unique[index] == 0:
            row[6:] = [None] * (len(ROW_FIELDS)-6)
        else:
            if n_positive[index] == 0:
                row[18] = None
            if n_positive[index] == n_unique[index]:
                row[19] = None
    return {'observed':list(observed), 'regime':regime,
            'shape':[len(model['alphabet'][e]) for e in observed], 'rows':packed}


def row_index(model, observed, assignment):
    if set(observed) != set(assignment):
        raise ValueError('Observation key must exactly match selected whole entries')
    index = 0
    for eid in observed:
        vector = tuple(assignment[eid])
        try:
            position = model['alphabet'][eid].index(vector)
        except ValueError:
            return None
        index = index * len(model['alphabet'][eid]) + position
    return index


def decode_witness(model, flat_index, regime='unknown', observed_f02=None):
    if flat_index is None:
        return None
    indices = np.unravel_index(flat_index, model['shape'])
    assignment = {eid:list(model['alphabet'][eid][int(j)]) for eid,j in zip(model['core'],indices)}
    labels = [s['id'] for s in model['states']]
    candidates = range(len(labels)) if regime == 'unknown' else [labels.index(regime)]
    compatible = [i for i in candidates if model['g_masks'][i].reshape(-1)[flat_index]]
    if not compatible:
        raise ValueError('Witness is not compatible with one complete shared state')
    if model['factor_f02']:
        vector = model['alphabet']['F02'][0] if observed_f02 is None else tuple(observed_f02)
        if vector not in model['alphabet']['F02']:
            raise ValueError('F02 observation outside source domain')
        assignment['F02'] = list(vector)
    return {'global_state':labels[compatible[0]], 'assignment':{eid:assignment[eid] for eid in IDS},
            'numerators_over_32':{name:int(values.reshape(-1)[flat_index]) for name,values in zip(TARGETS,model['scores'])}}


def logical_row(model, canonical_table, observed_ids, assignment):
    observed_ids = tuple(observed_ids)
    if observed_ids != tuple(e for e in IDS if e in observed_ids) or set(observed_ids) != set(assignment):
        raise ValueError('Select sorted whole entries and exactly their observed signatures')
    if any(not isinstance(assignment[e], (list,tuple)) or len(assignment[e]) != 4 or
           any(type(x) is not int or x not in (0,1,2) for x in assignment[e]) for e in observed_ids):
        raise ValueError('INPUT_ERROR: observations require complete capped four-integer signatures')
    core_observed = tuple(e for e in observed_ids if e in model['core'])
    if list(core_observed) != canonical_table['observed']:
        raise ValueError('Wrong canonical table')
    if any(tuple(assignment[e]) not in model['alphabet'][e] for e in observed_ids):
        return [0,0,0,0,0,0]+[None]*(len(ROW_FIELDS)-6)
    index = row_index(model, core_observed, {e:assignment[e] for e in core_observed})
    row = canonical_table['rows'][index].copy()
    if model['factor_f02'] and 'F02' not in observed_ids:
        factor = len(model['alphabet']['F02'])
        for column in (1,2,3,4):
            row[column] *= factor
    return row


def subsets(ids):
    return [tuple(ids[i] for i in range(len(ids)) if mask & (1 << i)) for mask in range(1 << len(ids))]
