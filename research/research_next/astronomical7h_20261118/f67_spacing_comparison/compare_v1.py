"""All-twelve spacing observations, not word identification. Read-only stdout."""
from pathlib import Path
import hashlib
import json

HERE=Path(__file__).resolve().parent

def main():
    receipt=json.loads((HERE/'projection_receipt_v1.json').read_text())
    for f in receipt['files']:
        assert hashlib.sha256((HERE/f['output']).read_bytes()).hexdigest()==f['output_sha256']
    guided=json.loads((HERE/'guided_observation_v1.json').read_text())
    image=json.loads((HERE/'image_observation_v1.json').read_text())
    assert len(guided['records'])==len(image['records'])==12
    result=[]
    for n,(g,i) in enumerate(zip(guided['records'],image['records'])):
        assert g['locator']==f'f67r2.{n+52}' and i['id']==f'W{n+1:02}'
        assert g['prior_bbox_xywh']==i['reading_bbox_xywh']
        pairs=[]
        for a in g['candidate_gap_review_regions']:
            x,y,w,h=a['bbox'];ab=[x,y,x+w,y+h]
            for b in i['candidate_gap_windows']:
                bb=b['original_image_xyxy']
                overlap=max(0,min(ab[2],bb[2])-max(ab[0],bb[0]))*max(0,min(ab[3],bb[3])-max(ab[1],bb[1]))
                pairs.append({'guided_candidate':a['id'],'image_candidate':b['id'],
                              'guided_xyxy':ab,'image_xyxy':bb,'rectangle_intersection_px2':overlap,
                              'meaning':'Candidate-window proximity only; not blank-pixel intersection, word boundary, or accuracy.'})
        assert g['word_boundary_certified'] is False and i['stable_word_boundary_separation'] is None
        result.append({'locator':g['locator'],'image_id':i['id'],'reading_bbox_xywh':i['reading_bbox_xywh'],
                       'identity_basis':'Both received this same prior reading envelope; not independent localization.',
                       'raw_versions':{v:g['versions'][v]['raw_line'] for v in ['ZL','IT']},
                       'guided_candidate_regions':g['candidate_gap_review_regions'],
                       'image_candidate_windows':i['candidate_gap_windows'],
                       'all_same_target_candidate_pairs':pairs,
                       'guided_assessment':g['boundary_assessment'],
                       'image_assessment':i['spacing_separation_assessment'],
                       'guided_grouping_alternatives':g['alternative_grouping_displays'],
                       'image_grouping_alternatives':i['reasonable_visual_grouping_alternatives'],
                       'word_boundary_truth':None,
                       'not_a_single_word_proof_if_no_candidate':True})
    out={'schema':'f67_spacing_comparison_v1','inputs':receipt['files'],'records':result,
         'summary':{'fixed_targets':12,'raw_source_lines':24,
                    'guided_candidate_regions':sum(len(r['guided_candidate_regions']) for r in result),
                    'image_candidate_windows':sum(len(r['image_candidate_windows']) for r in result),
                    'candidate_pairs':sum(len(r['all_same_target_candidate_pairs']) for r in result),
                    'positive_rectangle_pairs':sum(p['rectangle_intersection_px2']>0 for r in result for p in r['all_same_target_candidate_pairs']),
                    'word_boundary_certifications':0},
         'gate':'NO_STABLE_COMPLETE_WORD_BOUNDARY_ADJUDICATION_FROM_SPACING',
         'new_manuscript_word_matching_computed':False,
         'limits':['Same prior envelopes; not independent localization.',
                   'JPEG and TIFF are encodings of the same photograph, not independent evidence.',
                   'Same model system and exposed manuscript; not a new blind corpus or expert certification.',
                   'Candidates have different observation/selection granularity; counts are not votes.',
                   'Absence of a proposed cut does not prove a single word; visible gaps do not prove linguistic boundaries.']}
    print(json.dumps(out,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
