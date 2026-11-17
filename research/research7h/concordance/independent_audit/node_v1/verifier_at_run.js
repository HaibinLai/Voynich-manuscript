'use strict';
// Node pure-function comparison only. No DOM, browser, network, or source parser import.
const fs = require('fs');
const vm = require('vm');
const path = require('path');
const crypto = require('crypto');
const assert = require('assert');
const [dataPath, frontendPath, fixturePath, outputPath] = process.argv.slice(2);
assert(dataPath && frontendPath && fixturePath && outputPath);
assert(!fs.existsSync(outputPath), 'Use a new output directory; preserve earlier comparisons.');
fs.mkdirSync(outputPath, {recursive:true});
const sha = p => crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
const write = (name, value) => fs.writeFileSync(path.join(outputPath, name), JSON.stringify(value, null, 2) + '\n');
const plain = x => JSON.parse(JSON.stringify(x));
const data = JSON.parse(fs.readFileSync(dataPath));
const fixtures = JSON.parse(fs.readFileSync(fixturePath));
const context = vm.createContext({URLSearchParams});
vm.runInContext(fs.readFileSync(frontendPath, 'utf8'), context);
const query = vm.runInContext('(d,o)=>Concordance.query(d,o)', context);
const exportAll = vm.runInContext('(d,r,t)=>Concordance.buildExport(d,r,t)', context);
const parseParams = vm.runInContext('p=>Concordance.parseParams(p)', context);
const fields = ['status','groups','counts','page','page_count','page_size','page_items'];
const project = r => Object.fromEntries(fields.map(k => [k, plain(r[k])]));

try {
  const rawDifferences = [];
  for (let i=0;i<fixtures.length;i++) {
    const f=fixtures[i], actual=project(query(data,f.options));
    for (const key of fields) {
      if (JSON.stringify(actual[key]) !== JSON.stringify(f.expected[key])) rawDifferences.push({case:i,options:f.options,field:key,expected:f.expected[key],actual:actual[key]});
    }
  }
  write('original_fixture_differences.json',rawDifferences);
  // The original independent fixture used a minimum-one-page convention.
  // The product API uses ceil(records/50)=0 for no matches, with current page 1.
  // This display convention was not specified by the design; record the correction
  // separately without changing the frozen parser or original 46 fixtures.
  assert(rawDifferences.every(x => x.field==='page_count' && x.expected===1 && x.actual===0));
  write('zero_result_page_convention.json',{
    original_fixture_page_count:1, adopted_page_count:0, current_page_sentinel:1,
    definition:'page_count=ceil(filtered_record_count/50); current page stays 1 when page_count=0.',
    original_fixture_file_unchanged:true,
    scope:'Clarification of an unspecified zero-result pagination convention; no source, hit, slot or count changed.'
  });
  let exportRecords=0;
  const counterpartScan = new Map();
  for (const row of data.records) {
    const key=row.locator+'|'+row.version;
    if(!counterpartScan.has(key))counterpartScan.set(key,[]);
    counterpartScan.get(key).push(row);
  }
  for(const f of fixtures) {
    const expected=plain(f.expected);
    if(expected.counts.records===0)expected.page_count=0;
    const actual=query(data,f.options);
    assert.deepStrictEqual(project(actual),expected);
    const saved=plain(exportAll(data,actual,'2000-01-01T00:00:00.000Z'));
    assert.deepStrictEqual(saved.sources,data.sources);
    assert.deepStrictEqual(saved.counts,expected.counts);
    assert.strictEqual(saved.results.length,expected.groups.length);
    assert.strictEqual(saved.export_scope.all_filtered_matches,true);
    assert.strictEqual(saved.export_scope.exported_records,expected.groups.length);
    for(let i=0;i<expected.groups.length;i++) {
      const group=expected.groups[i], row=data.records[group.record_id], entry=saved.results[i];
      assert.deepStrictEqual(entry.record,row);
      assert.deepStrictEqual(entry.matching_slots,group.slots);
      assert.deepStrictEqual(entry.counterparts,counterpartScan.get(row.locator+'|'+(row.version==='ZL'?'IT':'ZL'))||[]);
    }
    exportRecords+=saved.results.length;
    const params=new URLSearchParams({q:f.options.q,v:f.options.v,mode:f.options.mode,
      folio:f.options.folio,type:f.options.type,uncertain:f.options.uncertain?'1':'0',page:String(f.options.page)});
    assert.deepStrictEqual(plain(parseParams(params.toString())),f.options);
  }

  // Exhaustive exact queries: derive expected groups from verified record slots,
  // independently of the frontend posting traversal.
  let exactQueries=0;
  for(const version of ['ZL','IT'])for(const retainUncertain of [true,false]) {
    const terms=new Map();
    const allTerms=new Set();
    for(const row of data.records)if(row.version===version) {
      const byTerm=new Map();
      for(let i=0;i<row.slots.length;i++) {
        const slot=row.slots[i],term=slot.normalized;
        if(term===null)continue;
        allTerms.add(term);
        const uncertain=slot.left_boundary==='uncertain'||slot.right_boundary==='uncertain';
        if(!retainUncertain&&uncertain)continue;
        if(!byTerm.has(term))byTerm.set(term,[]);
        byTerm.get(term).push(i);
      }
      for(const [term,slots] of byTerm) {
        if(!terms.has(term))terms.set(term,[]);
        terms.get(term).push({record_id:row.id,slots});
      }
    }
    for(const term of allTerms) {
      const expected=terms.get(term)||[];
      const actual=plain(query(data,{v:version,mode:'exact',q:term,uncertain:retainUncertain}));
      assert.deepStrictEqual(actual.groups,expected);
      assert.strictEqual(actual.counts.occurrences,expected.reduce((n,g)=>n+g.slots.length,0));
      assert.strictEqual(actual.counts.records,expected.length);
      assert.strictEqual(actual.counts.folios,new Set(expected.map(g=>data.records[g.record_id].folio)).size);
      assert.strictEqual(actual.counts.leaf_groups,new Set(expected.map(g=>data.records[g.record_id].leaf_group)).size);
      assert.strictEqual(actual.page_count,Math.ceil(expected.length/50));
      assert.deepStrictEqual(actual.page_items,expected.slice(0,50));
      exactQueries++;
    }
  }

  // Additional adversarial queries are literal, never regex/prototype properties.
  for(const q of ['constructor','__proto__','<script>','.*','?','[','😀',' ',"q'o",'q’o'])for(const version of ['ZL','IT']) {
    const actual=plain(query(data,{v:version,mode:'literal',q}));
    const expected=data.records.filter(r=>r.version===version&&r.display.includes(q)).map(r=>({record_id:r.id,slots:[]}));
    assert.deepStrictEqual(actual.groups,expected);
    assert.strictEqual(actual.counts.occurrences,null);
  }
  const result={completed_utc:new Date().toISOString(),all_passed:true,
    fixture_cases:fixtures.length,exhaustive_exact_queries:exactQueries,additional_literal_queries:20,
    export_record_instances_checked:exportRecords,all_exports_include_every_filtered_group:true,
    url_roundtrips:fixtures.length,original_fixture_page_convention_differences:rawDifferences.length,
    hashes:{data:sha(dataPath),frontend:sha(frontendPath),fixtures:sha(fixturePath),verifier:sha(__filename)},
    browser_test_performed:false,dom_or_download_click_performed:false,
    scope:'Pure query/export/URL API checks in Node VM; original records and sources unchanged; no browser or scientific scoring.'};
  write('audit_report.json',result);
  console.log(JSON.stringify(result));
} catch(error) {
  write('failure.json',{message:String(error),stack:error.stack,hashes:{data:sha(dataPath),frontend:sha(frontendPath),fixtures:sha(fixturePath),verifier:sha(__filename)}});
  throw error;
}
