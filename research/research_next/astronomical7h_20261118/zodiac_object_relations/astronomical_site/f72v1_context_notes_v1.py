from record_helpers import *
d=load('f72v1');s=seed('f72v1');native=['f72v1:V2:1:1','f72v1:V2:1:2','f72v1:V2:2:1','f72v1:V2:2:2']
notes={
'C01':'Outer writing course is visible around the diagram, with an upper-right rubbed dark patch and right fold retained. An envelope is not an ink path, and local loss is not repaired.',
'C02':'Writing course between human bands is interrupted at the right-side material hole. Exposed lower-layer marks are not treated as continuation on the front surface.',
'C03':'Small circular writing surrounds the central beam/cup assembly. The darker short run below and between the cups remains a separate fixed text region; no name or reading assigned.',
'R01':'Central beam/upright and two suspended cup-like forms are separately visible with blue details. Four supplementary whole/component envelopes preserve this context without asserting a historical identity or exclusive text ownership.',
'R02':'The broad bottom margin was actually inspected at native detail in two overlapping tiles and external-region views. Two separate dark/scratch-like candidates are retained, with no local object or leader positively resolved.',
'D01':'Actual irregular material hole exposes another layer and disrupts annular boundary and nearby head/figure/short marks. No missing stroke is restored or extrapolated; exposed marks are not front-surface replacements.',
'D02':'Rubbed dark patch above the crowned-looking outer figure overlaps the outer writing neighborhood. Smear is retained as damage context, not a new symbol or connecting line.',
'D03':'Vertical fold crosses upper-right figures and ring courses toward the hole. Distinct local hand endpoints outside it and unresolved endpoints near it are recorded separately; no blanket repair.'}
for category in ['continuous_ring_writing_original','context_regions_original','gaps_and_damage_original']:
 for r in s[category]:
  vids=native if r['id']!='R02' else ['f72v1:V2-extra:context:2:tile1','f72v1:V2-extra:context:2:tile2','f72v1:ZE01:V3','f72v1:ZE02:V3']
  d['context_reviews'].append({'context_uid':'f72v1:context:'+r['id'],'original_category':category,'original_id':r['id'],'original_record':r,'review_status':'reviewed','view_ids':vids,'observation_facts':[notes[r['id']]],'limitations':['Original context record preserved; envelopes are not ink masks or semantic ownership regions.']})
d['context_reviews'].append({'context_uid':'f72v1:unfilled-original','original_category':'unfilled_regions_original','original_record':s.get('unfilled_regions_original'),'review_status':'reviewed','view_ids':native,'observation_facts':['Original null retained. Blank arcs do not generate missing regular-angle figures or text slots.']})
d['open_arc_notes']=['Outer and inner text fields vary in width; no equal-angle completion or implied missing object is introduced.','Right-side hole and folds interrupt courses and local figure neighborhoods; an apparent gap is not repaired into a closed boundary.','Bottom margin retains ZE01/ZE02 as separate observed candidates with no local object association; blank space is not an unviewed NA.']
for ident in ['ZI02','ZI03']:
 next(r for r in d['text_records'] if r['region_uid']=='f72v1:'+ident)['damage_refs']=['f72v1:context:D01']
d['limitations']+=['All 71 planned views and 3 explicit native expansions actually displayed; no other observers new relation judgments read before freeze.','All text-to-object edges remain local layout evidence only. A body-to-pointed E never becomes a text-to-object E.','Three neighboring-star competitors retained separately: O07 to O06 star has unresolved head-side/bent-arm endpoint P; O08 to O07 and I04 to I03 are spatial N only.','Native evidence rectangles bound visible sections without claiming pixel-exact ink paths; unknown intervals are not interpolated.']
save('f72v1',d)
