export function validateOffer(input) {
  if (!input || typeof input !== 'object' || Array.isArray(input)) throw Error('Offer object required');
  const title = String(input.title ?? '').trim();
  if (!title) throw Error('Offer title required');
  if (input.conflict) throw Error('BLOCKED — FACT CONFLICT');
  if (input.price != null && input.priceVerified !== true) throw Error('BLOCKED — UNVERIFIED PRICE');
  if (input.date != null && input.dateVerified !== true) throw Error('BLOCKED — UNVERIFIED DATE');
  const destination = String(input.destination ?? title).trim();
  const cta = String(input.cta ?? 'Напишите нам, чтобы узнать подробности').trim();
  return {title, destination, cta, price:input.price ?? null, date:input.date ?? null};
}
export function generateHooks(input) {
  const {destination:d} = validateOffer(input);
  return [
    `Что важно знать о поездке: ${d}?`,
    `${d}: идея для следующего путешествия`,
    `Планируете путешествие? Присмотритесь: ${d}`,
    `Почему стоит узнать больше: ${d}`,
    `${d}: детали, которые имеют значение`
  ];
}
export function createStoryboard(input, selectedHook = 0, customHooks = null) {
  const o = validateOffer(input);
  const hooks = customHooks ?? generateHooks(input);
  if (!Array.isArray(hooks) || hooks.length !== 5 || hooks.some(h=>typeof h !== 'string' || !h.trim())) throw Error('Exactly five nonempty hooks required');
  if (!Number.isInteger(selectedHook) || selectedHook < 0 || selectedHook > 4) throw Error('Hook index must be 0..4');
  const details = [o.title];
  if (o.date != null) details.push(`Даты: ${o.date}`);
  if (o.price != null) details.push(`Цена: ${o.price}`);
  return {format:'SILENT', width:1080,height:1920,fps:30,scenes:[
    {text:hooks[selectedHook],seconds:4},
    {text:details.join('\n'),seconds:6},
    {text:o.cta,seconds:4}
  ]};
}
