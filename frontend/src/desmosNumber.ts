/** Expand JS exponent notation into a decimal literal understood by Desmos. */
export function desmosNumber(value:number):string{
 if(!Number.isFinite(value))throw new RangeError('Desmos parameter must be finite');
 const raw=String(value);
 if(!/[eE]/.test(raw))return raw;
 const [mantissa,exponent]=raw.toLowerCase().split('e');
 const negative=mantissa.startsWith('-');
 const unsigned=negative?mantissa.slice(1):mantissa;
 const point=unsigned.indexOf('.');
 const digits=unsigned.replace('.','');
 const position=(point<0?unsigned.length:point)+Number(exponent);
 const decimal=position<=0?'0.'+'0'.repeat(-position)+digits:position>=digits.length?digits+'0'.repeat(position-digits.length):digits.slice(0,position)+'.'+digits.slice(position);
 return (negative?'-':'')+decimal;
}
