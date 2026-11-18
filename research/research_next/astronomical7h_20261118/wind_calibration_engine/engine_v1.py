"""Pure token/block arithmetic for a future explicitly approved input contract.

NO file, network, stdin, catalogue, image, geographic or real-input loader exists
here. The companion runner uses artificial fixtures only. Importing this module
does not authorize manuscript scoring. Tokens and identities must already have
been defined/frozen by a separately reviewed input layer; this engine never
normalizes, tokenizes, emends, guesses IDs or establishes historical meaning.
"""
from __future__ import annotations
from collections import Counter
from dataclasses import dataclass
from fractions import Fraction
from typing import Mapping, Sequence

N = 12

class DefinitionError(ValueError):
    """A label/group/boundary is undefined; it is not a binary measurement NA."""

@dataclass(frozen=True)
class Unknown:
    identity: str

@dataclass(frozen=True)
class Name:
    tokens: tuple[str, ...] | None

@dataclass(frozen=True)
class Block:
    items: tuple[str | Unknown, ...] | None

@dataclass(frozen=True)
class BodyGroup:
    blocks: tuple[Block, ...] | None

@dataclass(frozen=True)
class CellEvidence:
    value: int | None
    # Positions count supplied block items, including Unknown placeholders.
    # They are NOT original source-token, glyph or image positions.
    known_occurrences: tuple[tuple[int, int, int], ...]
    unknown_identities: tuple[str, ...]
    reason: str

@dataclass(frozen=True)
class MatrixEvidence:
    name_ids_in_cycle: tuple[str, ...]
    self_paired_body_ids_in_cycle: tuple[str, ...]
    values: tuple[tuple[int | None, ...], ...]
    cells: tuple[tuple[CellEvidence, ...], ...]
    unknown_occurrence_counts: tuple[tuple[str, int], ...]


def _atom(value: object) -> bool:
    return isinstance(value, str) and bool(value) and not any(c.isspace() for c in value)


def _validate_name(name: Name) -> None:
    if not isinstance(name, Name):
        raise TypeError('Expected a Name whose tokens were already defined.')
    if name.tokens is None or name.tokens == ():
        raise DefinitionError('A complete nonempty name unit is not defined.')
    if not isinstance(name.tokens, tuple) or not all(_atom(token) for token in name.tokens):
        raise ValueError('Name tokens must be an explicit tuple of nonempty, whitespace-free atoms.')


def _validate_group(group: BodyGroup) -> None:
    if not isinstance(group, BodyGroup):
        raise TypeError('Expected a BodyGroup with predefined independent blocks.')
    if group.blocks is None:
        raise DefinitionError('Body-group content or block boundaries are not defined.')
    if not isinstance(group.blocks, tuple):
        raise ValueError('Blocks must be an explicit tuple.')
    for block in group.blocks:
        if not isinstance(block, Block):
            raise TypeError('Each independent block must be a Block.')
        if block.items is None:
            raise DefinitionError('A block is not defined; use Unknown only for defined units with missing text.')
        if not isinstance(block.items, tuple):
            raise ValueError('Block items must be an explicit tuple.')
        for item in block.items:
            if isinstance(item, Unknown):
                if not _atom(item.identity):
                    raise ValueError('Unknown identities must be explicit, nonempty atoms.')
            elif not _atom(item):
                raise ValueError('Known block tokens must be nonempty, whitespace-free atoms.')


def match_complete_name(name: Name, group: BodyGroup) -> CellEvidence:
    """Exact contiguous complete-token occurrence, with independent block barriers.

    Unknown may contain any sequence, possibly empty, but it never certifies a
    bridge. Absence with any unknown remains measurement NA. A witnessed known
    occurrence always establishes binary 1, irrespective of other unknowns.
    """
    _validate_name(name)
    _validate_group(group)
    assert name.tokens is not None and group.blocks is not None
    length = len(name.tokens)
    occurrences = []
    unknown_ids = set()
    for block_index, block in enumerate(group.blocks):
        assert block.items is not None
        items = block.items
        unknown_ids.update(item.identity for item in items if isinstance(item, Unknown))
        for start in range(len(items) - length + 1):
            if all(isinstance(items[start + k], str) and items[start + k] == token
                   for k, token in enumerate(name.tokens)):
                occurrences.append((block_index, start, start + length))
    value = 1 if occurrences else None if unknown_ids else 0
    reason = ('known_complete_occurrence' if occurrences else
              'no_known_occurrence_with_measurement_unknown' if unknown_ids else
              'fully_defined_known_text_without_occurrence')
    return CellEvidence(value, tuple(occurrences), tuple(sorted(unknown_ids)), reason)


def construct_twelve_matrix(names: Mapping[str, Name], groups: Mapping[str, BodyGroup],
                            name_cycle: Sequence[str], self_pairing: Mapping[str, str]) -> MatrixEvidence:
    """Use an explicit bijection and cycle; IDs themselves have no ordering meaning."""
    cycle = tuple(name_cycle)
    if len(cycle) != N or len(set(cycle)) != N or set(cycle) != set(names):
        raise DefinitionError('Exactly twelve explicitly ordered unique name IDs are required.')
    if not all(_atom(identity) for identity in cycle) or not all(_atom(identity) for identity in groups):
        raise ValueError('All supplied name/body identities must be explicit atoms.')
    if set(self_pairing) != set(names):
        raise DefinitionError('Self-pairing must explicitly cover all twelve name IDs.')
    body_cycle = tuple(self_pairing[identity] for identity in cycle)
    if len(groups) != N or len(set(body_cycle)) != N or set(body_cycle) != set(groups):
        raise DefinitionError('Self-pairing must be a bijection onto twelve defined body groups.')
    # Validate every input before constructing a single matrix cell.
    for identity in cycle:
        _validate_name(names[identity])
    for identity in body_cycle:
        _validate_group(groups[identity])
    cells = tuple(tuple(match_complete_name(names[ni], groups[bi]) for bi in body_cycle)
                  for ni in cycle)
    unknown_counts = Counter()
    for identity in body_cycle:
        for block in groups[identity].blocks:
            unknown_counts.update(item.identity for item in block.items if isinstance(item, Unknown))
    return MatrixEvidence(cycle, body_cycle, tuple(tuple(cell.value for cell in row) for row in cells),
                          cells, tuple(sorted(unknown_counts.items())))


def _matrix(values: Sequence[Sequence[int | None]]) -> tuple[tuple[int | None, ...], ...]:
    result = tuple(tuple(row) for row in values)
    if len(result) != N or any(len(row) != N for row in result):
        raise ValueError('The mathematical matrix must be exactly twelve by twelve.')
    if any(value is not None and (type(value) is not int or value not in (0, 1))
           for row in result for value in row):
        raise ValueError('Matrix cells must be 0, 1 or defined-unit measurement None; booleans are rejected.')
    return result


def _linear_interval(values: tuple[tuple[int | None, ...], ...],
                     weight) -> dict:
    lower = Fraction(0)
    upper = Fraction(0)
    missing = 0
    for i, row in enumerate(values):
        for j, value in enumerate(row):
            coefficient = weight(i, j)
            if value is None:
                lower += min(Fraction(0), coefficient)
                upper += max(Fraction(0), coefficient)
                missing += 1
            else:
                lower += coefficient * value
                upper += coefficient * value
    return {'point': lower if not missing else None, 'lower': lower, 'upper': upper,
            'unknown_cells': missing,
            'qualification': 'exact' if not missing else 'conservative_independent_cell_relaxation_not_asserted_sharp'}


def describe_twelve_phases(values: Sequence[Sequence[int | None]]) -> dict:
    """Pure matrix arithmetic, conditional on already-defined binary units.

    This low-level mathematical function cannot know whether a supplied None
    hides a definition failure. The validated pipeline is evaluate_twelve();
    it rejects undefined names or block boundaries before matrix construction.
    No rank or tie set is fabricated from incomplete phase intervals.
    """
    values = _matrix(values)
    phases = []
    for shift in range(N):
        cells = tuple(values[i][(i + shift) % N] for i in range(N))
        hits = sum(value == 1 for value in cells)
        missing = sum(value is None for value in cells)
        phases.append({'shift': shift, 'known_hits': hits, 'measurement_unknowns': missing,
                       'point': Fraction(hits, N) if not missing else None,
                       'lower': Fraction(hits, N), 'upper': Fraction(hits + missing, N),
                       'denominator': N})
    nonself = _linear_interval(values, lambda i, j: Fraction(1, N) if i == j else Fraction(-1, N*(N-1)))
    all_phases = _linear_interval(values, lambda i, j: Fraction(N-1, N*N) if i == j else Fraction(-1, N*N))
    complete = all(phase['point'] is not None for phase in phases)
    ties = None
    means = {'nonself': None, 'all_phases': None}
    if complete:
        points = tuple(phase['point'] for phase in phases)
        h = sum(value > points[0] for value in points)
        e = sum(value == points[0] for value in points)
        ties = {'strictly_above_self': h, 'equal_to_self_including_self': e,
                'self_rank_interval': (h+1, h+e),
                'maximizing_shifts': tuple(s for s, value in enumerate(points) if value == max(points)),
                'descriptive_upper_tail_fraction_not_p_value': Fraction(h+e, N)}
        means = {'nonself': sum(points[1:], Fraction(0))/(N-1),
                 'all_phases': sum(points, Fraction(0))/N}
    return {'N': N, 'complete_point_statistics_available': complete, 'phases': tuple(phases),
            'self_point': phases[0]['point'], 'means': means,
            'Delta_nonself_primary': nonself, 'Delta_all_phases_auxiliary': all_phases,
            'endpoint_relation': 'Delta_nonself = (12/11) * Delta_all_phases',
            'ties': ties,
            'missingness_limit': 'Any incomplete bounds relax binary cells independently. Shared or other textual constraints can make endpoints unattainable; no joint rank or sharpness claim.',
            'inference_limit': 'Descriptive cyclic transforms of one constructed matrix, not independent samples, a permutation p-value, semantic correctness or glyph certification.'}


def evaluate_twelve(names: Mapping[str, Name], groups: Mapping[str, BodyGroup],
                    name_cycle: Sequence[str], self_pairing: Mapping[str, str]) -> dict:
    matrix = construct_twelve_matrix(names, groups, name_cycle, self_pairing)
    statistics = describe_twelve_phases(matrix.values)
    return {'matrix': matrix, 'statistics': statistics,
            'shared_unknown_identities': tuple((identity, count) for identity, count in matrix.unknown_occurrence_counts if count > 1),
            'real_input_authorization': 'No actual-input loader or authorization supplied by this module.'}
