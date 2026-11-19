"""Exact subset summaries and minimality; finite model cardinalities, never probabilities."""
from itertools import product
from core_v1 import IDS, CLASS_NAMES, logical_row, subsets


def mask_of(selected, order=IDS):
    return sum(1 << i for i,eid in enumerate(order) if eid in selected)


def inclusion_minimal(masks):
    masks = sorted(set(masks))
    return [m for m in masks if not any(t != m and (t & m) == t for t in masks)]


def minima_record(masks):
    result = inclusion_minimal(masks)
    return {'inclusion_minimal_masks':result,
            'minimum_entry_count':min((bin(m).count('1') for m in result),default=None),
            'all_inclusion_minimal_sets':[[eid for i,eid in enumerate(IDS) if m & (1<<i)] for m in result]}


def summarize(model, tables):
    """tables indexed by (regime, core_mask); exact F02 expansion covers all64."""
    regimes = ['unknown'] + [s['id'] for s in model['states']]
    regime_rows = {}
    for regime in regimes:
        rows = []
        for selected in subsets(IDS):
            full_mask = mask_of(selected)
            core_mask = mask_of(selected,model['core'])
            raw = tables[regime,core_mask]['rows']
            factor = len(model['alphabet']['F02']) if model['factor_f02'] and 'F02' in selected else 1
            counts = {name:sum(r[0] == c for r in raw)*factor for c,name in enumerate(CLASS_NAMES)}
            feasible = sum(counts[name] for name in CLASS_NAMES[1:])
            rows.append({'mask':full_mask,'observed':list(selected),'canonical_core_mask':core_mask,
                         'F02_observed': 'F02' in selected,'feasible_outcome_count':feasible,
                         'class_counts':counts,
                         'ambient_outcome_count':sum(counts.values()),
                         'ambient_conflict_count_not_an_empirical_rate':counts['CONFLICT'],
                         'every_feasible_outcome_decisive':feasible>0 and counts['MIXED']==0,
                         'some_all_joint_positive':counts['ALL_JOINT_POSITIVE']>0,
                         'some_none_joint_positive':counts['NONE_JOINT_POSITIVE']>0,
                         'some_decisive':counts['ALL_JOINT_POSITIVE']+counts['NONE_JOINT_POSITIVE']>0})
        minima = {}
        for key in ('some_all_joint_positive','some_none_joint_positive','some_decisive','every_feasible_outcome_decisive'):
            minima[key] = minima_record(r['mask'] for r in rows if r[key])
        singletons = []
        for row in rows:
            if len(row['observed']) == 1:
                label = ('ALL_OUTCOMES_UNRESOLVED' if not row['some_decisive'] else
                         'ALL_FEASIBLE_OUTCOMES_DECISIVE' if row['every_feasible_outcome_decisive'] else
                         'SOME_DECISIVE_NOT_GUARANTEED')
                singletons.append({'entry':row['observed'][0],'classification':label,
                                   'feasible_outcome_count':row['feasible_outcome_count'],'class_counts':row['class_counts']})
        regime_rows[regime] = {'subsets':rows,'minimal_sets':minima,'singletons':singletons}
    known = regimes[1:]
    both_guaranteed = [m for m in range(64) if all(regime_rows[g]['subsets'][m]['every_feasible_outcome_decisive'] for g in known)]
    return {'schema':'whole_entry_information_summary_v1','regimes':regime_rows,
            'guaranteed_decisive_for_each_possible_known_g':minima_record(both_guaranteed),
            'counts_are_finite_model_cardinalities_not_probabilities':True,
            'F02_factorization_scope':'Only H/H4/difference and their joint predicate; not single-pair similarities incident to F02.'}


def local_certificates(model, tables, regime, observed_ids, assignment):
    """Return all inclusion-minimal subsets retaining this same decisive category."""
    selected = tuple(observed_ids)
    parent_mask = mask_of(selected)
    parent = logical_row(model,tables[regime,mask_of(selected,model['core'])],selected,assignment)
    target = parent[0]
    if target not in (1,3):
        return {'parent_class':CLASS_NAMES[target],'inclusion_minimal_masks':[],
                'reason':'Local decisive certificates require a feasible already-decisive parent observation.'}
    candidates = []
    for subset in subsets(IDS):
        mask = mask_of(subset)
        if mask & parent_mask != mask:
            continue
        row = logical_row(model,tables[regime,mask_of(subset,model['core'])],subset,{e:assignment[e] for e in subset})
        if row[0] == target:
            candidates.append(mask)
    return {'parent_class':CLASS_NAMES[target],**minima_record(candidates),
            'same_observation_projected_to_every_subset':True}
