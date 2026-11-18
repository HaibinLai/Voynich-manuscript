from record_helpers import *
d=load('f72r3');s=seed('f72r3');native=['f72r3:V2:1:1','f72r3:V2:1:2','f72r3:V2:2:1','f72r3:V2:2:2']
notes={
'C01':'Outer circumferential writing remains a continuous intended course but locally pale/fold-disturbed; exact ink continuity and historical reading origin are not certified. All margins checked in native extended views.',
'C02':'Course between outer and middle figures is visible above and below, but not a fully drawn exclusive compartment in every left-side gap. Candidate judgments use visible boundaries rather than ring labels alone.',
'C03':'Writing course separates middle and inner fields; local paper folds and body/strand intersections retained. Bounding inner/outer envelopes are not glyph paths or ownership masks.',
'C04':'Small circular writing encloses the paired colored central forms. Dark short run below the red form remains a separate fixed text record; surrounding circular text is not assigned to one colored component.',
'R01':'Two differently colored segmented nonhuman forms and their limb-like lines are separately visible; no species/name assigned. Dark run is in the immediate lower red-form pocket, with whole-scene interpretation unresolved.',
'R02':'Neighboring-panel fragments in left overlap were actually viewed for context and explicitly excluded from target component additions. No cross-page word comparison performed.',
'R03':'Complete target perimeter and margins were inspected at native detail through overlapping extended tiles. No additional separate prose block was positively identified; this is bounded visual observation, not proof of semantic absence.',
'D01':'Strong nearly vertical fold obscures body/hand/star and writing detail in right fields. E/P/NA distinctions preserve these limits without enhancement or repaired pixels.',
'D02':'Left joint/overlap and pale edge are paper context. Neighboring-panel bodies and stars are not silently imported into target candidates.',
'D03':'Lower crease crosses body/text neighborhoods and diminishes line contrast. In particular, the O08 seed pointed rectangle is retained but not confirmed as a distinct star after native and expanded review.'}
for category in ['continuous_ring_writing_original','context_regions_original','gaps_and_damage_original']:
 for r in s[category]:
  vids=native
  if r['id']=='R02':vids=['f72r3:V2-extra:context:2']
  if r['id']=='R03':vids=['f72r3:V2-extra:context:3:tile'+str(i) for i in range(1,5)]
  d['context_reviews'].append({'context_uid':'f72r3:context:'+r['id'],'original_category':category,'original_id':r['id'],'original_record':r,'review_status':'reviewed','view_ids':vids,'observation_facts':[notes[r['id']]],'limitations':['Source envelopes/descriptions retained exactly as source context; no ink masks, text authentication or semantic scores.']})
d['context_reviews'].append({'context_uid':'f72r3:unfilled-original','original_category':'unfilled_regions_original','original_record':s.get('unfilled_regions_original'),'review_status':'reviewed','view_ids':native,'observation_facts':['Original null preserved. Broad annular gaps do not generate missing figure/text slots.']})
d['open_arc_notes']=['Right-side broad outer gap (ZO04) retains the long writing track and fading star strand; no missing regular-angle object supplied.','Left-side broad gap retains ZO09/ZU01, visible middle-body/star competitors and interrupted course context; ring labels alone do not certify exclusions.','Lower creases and pale fields are retained; no circular closure or historical start direction inferred.']
for ident in ['ZO02','ZO03','ZO04','ZO05','ZM02','ZM03','ZM04','ZM05']:
 next(r for r in d['text_records'] if r['region_uid']=='f72r3:'+ident)['damage_refs']=['f72r3:context:D01']
for ident in ['ZO06','ZO07','ZO08']:
 next(r for r in d['text_records'] if r['region_uid']=='f72r3:'+ident)['damage_refs']=['f72r3:context:D03']
d['limitations'] += ['All 77 planned views and 3 explicit native expansions actually displayed; no new peer relation judgments read before freeze.','Two fixed pointed components are NA_after_review: O08 source box unconfirmed as a distinct pointed form, M05 original null retained. This is not a completed star/person pairing.','O08 to neighboring M07 star is separately retained at N only; a middle-body E is not transferred to another body.','All text-to-object edges remain local layout evidence, never naming passes. Auxiliary curves and ambiguous ray-writing contact are recorded separately.']
save('f72r3',d)
