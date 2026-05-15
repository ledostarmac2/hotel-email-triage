export type RedactionSummary = {
  cardNumbers: number;
  cvvValues: number;
  expiryDates: number;
  authorizationTokens: number;
};

export type RedactionResult = {
  text: string;
  summary: RedactionSummary;
};

const possibleCardPattern = /(?:\d[ -]*?){13,19}/g;
const cvvPattern = /\b(?:cvv|cvc|security code)\s*[:#-]?\s*\d{3,4}\b/gi;
const expiryPattern = /\b(?:exp(?:iry|iration)?\.?\s*)?(?:0[1-9]|1[0-2])\s*[/.-]\s*(?:\d{2}|\d{4})\b/gi;
const authTokenPattern = /\b(?:authorization|sertifi|cca|credit card auth(?:orization)?)\s+(?:link|token|code)\s*[:#-]?\s*[A-Za-z0-9_-]{8,}\b/gi;

export function redactSensitivePaymentData(input: string): RedactionResult {
  const summary: RedactionSummary = {
    cardNumbers: 0,
    cvvValues: 0,
    expiryDates: 0,
    authorizationTokens: 0
  };

  let text = input.replace(possibleCardPattern, (match) => {
    const digits = match.replace(/\D/g, "");
    if (!isLikelyPaymentCard(digits)) return match;
    summary.cardNumbers += 1;
    return "[REDACTED_CARD]";
  });

  text = text.replace(cvvPattern, () => {
    summary.cvvValues += 1;
    return "[REDACTED_CVV]";
  });

  text = text.replace(expiryPattern, (match) => {
    if (!/exp|\/|\.|-/i.test(match)) return match;
    summary.expiryDates += 1;
    return "[REDACTED_EXPIRY]";
  });

  text = text.replace(authTokenPattern, () => {
    summary.authorizationTokens += 1;
    return "[REDACTED_PAYMENT_AUTHORIZATION]";
  });

  return { text, summary };
}

function isLikelyPaymentCard(digits: string) {
  if (digits.length < 13 || digits.length > 19) return false;
  if (/^(\d)\1+$/.test(digits)) return false;
  return passesLuhn(digits);
}

function passesLuhn(digits: string) {
  let sum = 0;
  let shouldDouble = false;

  for (let index = digits.length - 1; index >= 0; index -= 1) {
    let digit = Number(digits[index]);
    if (shouldDouble) {
      digit *= 2;
      if (digit > 9) digit -= 9;
    }
    sum += digit;
    shouldDouble = !shouldDouble;
  }

  return sum % 10 === 0;
}
