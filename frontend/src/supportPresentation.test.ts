import {expect,it} from 'vitest';
import {supportLabel} from './supportPresentation';
it('distinguishes unreviewed plans, suggestions and supplied-source support',()=>{
 const item={text:'Prepare.',evidence_ids:[]};
 expect(supportLabel({...item,support_status:'unreviewed'},'en')).toBe('');
 expect(supportLabel({...item,support_status:'planning_suggestion'},'en')).toBe('Suggested next step');
 expect(supportLabel({...item,support_status:'source_supported'},'en')).toBe('Based on the supplied source');
 expect(supportLabel(item,'bn')).toBe('');
});
