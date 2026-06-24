export function newRequestId(): string {
  return crypto.randomUUID();
}
