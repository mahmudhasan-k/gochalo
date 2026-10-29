import {expect,it} from 'vitest';
import {formatCreated} from './sessionDate';
it('shows the creation date and minute in the chosen language',()=>{
 const value=new Date(2025,7,4,8,57).toISOString();
 expect(formatCreated(value,'en')).toBe('4 August 2025 · 8:57am');
 expect(formatCreated(value,'bn')).toContain('২০২৫');
 expect(formatCreated(value,'bn')).toContain('৮:৫৭');
 expect(formatCreated('invalid','en')).toBe('');
});
