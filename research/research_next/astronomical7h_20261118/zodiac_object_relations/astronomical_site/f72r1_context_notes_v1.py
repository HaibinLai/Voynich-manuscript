from record_helpers import *
d=load('f72r1');s=seed('f72r1');native=['f72r1:V2:1:1','f72r1:V2:1:2','f72r1:V2:2:1','f72r1:V2:2:2']
notes={
'R_central':'Continuous circular writing around the central animal/basket scene separates it from inner figures. Retain its full bounding envelope, not a glyph path or a closed ownership assignment.',
'R_middle':'Circular writing is visible between inner and outer figures, with body outlines often resting on or crossing the course. Left fold and hole limit local visibility; surface differences retained without reconstruction.',
'R_outer':'Outermost circular writing surrounds the complete inspected target. Native overlapping grid retains pale lower and left arcs; adjacent diagram writing is off-target. No historical reading origin/direction inferred.',
'C_animal':'Central reddish quadruped and separate green-topped basket-like form are visible. Under-belly dark run is a local scene candidate only; no animal species or text meaning assigned.',
'C_short_dark':'Compact dark run under the belly has been reviewed as the fixed supplemental text record. It is distinct from the circular writing and has no observed graphic text leader.',
'H_underlying_marks':'Dark marks visible through the hole lie on another surface. They are preserved as off-surface context, excluded from front-panel text and from any bridge across missing body strokes.',
'A_hole':'Real missing parchment cuts I05 body/arm neighborhood. Visible head/container remnants and raised arm are retained separately; no reconstructed connection across the hole. Body-to-pointed evidence stays partial.',
'A_vertical_fold':'Vertical fold crosses the upper-left body field and lies near the hole. It is a paper feature, not an intentional divider, leader or body contour.',
'A_left_page_joint':'Left page joint is physically visible in native context. Neighboring panel contours beyond it are retained only as off-target context, not selected as local endpoint candidates.',
'A_right_discoloration':'Background stain and pale paper patches near the right edge reduce contrast without adding a text or object endpoint. Nearby figures and full writing zones remain in the roster.',
'A_bottom_gap':'Wide bottom arc contains separated writing groups and open parchment between flanking outer bodies. No regular-angle body/label slot is added; both neighboring body/star contexts remain explicit alternatives.'}
for category in ['continuous_ring_writing_original','context_regions_original','gaps_and_damage_original']:
 for r in s[category]:d['context_reviews'].append({'context_uid':'f72r1:context:'+r['id'],'original_category':category,'original_id':r['id'],'original_record':r,'review_status':'reviewed','view_ids':native,'observation_facts':[notes[r['id']]],'limitations':['Original rectangle is context envelope, not an ink mask; source description preserved separately from current visual fact.']})
d['context_reviews'].append({'context_uid':'f72r1:unfilled-original','original_category':'unfilled_regions_original','original_record':s.get('unfilled_regions_original'),'review_status':'reviewed','view_ids':native,'observation_facts':['Original null retained; no additional region inferred from regularity.']})
d['open_arc_notes']=['A_bottom_gap: Broad lower arc with separate writing clusters, flanked by existing bodies. No circular closure, missing slot or object inferred. Actually reviewed in ZO06:V3 and V2:2:1/V2:2:2.']
seg=next(x for x in d['line_segments'] if x['segment_uid']=='f72r1:I05:visible-hand-path')
seg['breaks_or_occlusions']=[{'box_xyxy':[2705,1230,2865,1455],'reason':'Physical hole removes body/arm continuity. Underlying ink is on another surface and cannot bridge the gap.'}]
r=next(x for x in d['object_component_reviews'] if x['component_uid']=='f72r1:I05/body');r['missing_component_state']='Head and torso/container remnants visible; substantial body/arm junction removed by physical hole. Original full seed envelope is retained, not proof of a complete body.'
d['limitations'] += ['All 42 planned displays actually viewed; V0/V1 are navigation overviews and never substituted for native V2/V3/V4 evidence.','Annular text has multiple local layout candidates without text-origin leaders. Body-to-pointed E is not transferred to text-to-object edges.','I05 missing parchment and off-surface marks preserve partial graphic status; no reconstruction.']
save('f72r1',d)
