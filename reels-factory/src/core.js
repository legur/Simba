export function validateOffer(offer) {
  if (!offer || typeof offer !== 'object') throw new Error('Offer object required');
  const title = String(offer.title || '').trim();
  if (!title) throw new Error('Offer title required');
  if (offer.conflict === true) throw new Error('BLOCKED — FACT CONFLICT');
  if (offer.price != null && !offer.priceVerified) throw new Error('Unverified price');
  if (offer.date != null && !offer.dateVerified) throw new Error('Unverified date');
  return { title, destination: String(offer.destination || title).trim(), price: offer.price ?? null, date: offer.date ?? null, cta: String(offer.cta || 'Узнайте подробности').trim() };
}
export function generateHooks(offer) {
  const o = validateOffer(offer);
  const place = o.destination;
  return [
    `Что стоит знать о поездке в ${place}?`,
    `${place}: идея для следующего путешествия`,
    `Планируете поездку в ${place}?`,
    `Три причины присмотреться к ${place}`,
    `${place}: подробности, которые важно проверить`
  ];
}
export function createStoryboard(offer, selectedHook = 0) {
  const o = validateOffer(offer);
  const hooks = generateHooks(offer);
  if (!Number.isInteger(selectedHook) || selectedHook < 0 || selectedHook >= hooks.length) throw new Error('Invalid hook index');
  const middle = [o.title];
  if (o.date != null) middle.push(`Даты: ${o.date}`);
  if (o.price != null) middle.push(`Цена: ${o.price}`);
  return { format: 'SILENT', scenes: [
    {text:hooks[selectedHook],seconds:4},
    {text:middle.join('\\n'),seconds:6},
    {text:o.cta,seconds:4}
  ] };
}
