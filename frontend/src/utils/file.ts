export function getFileUrl(path: string): string {
  if (/^https?:\/\//i.test(path)) return path
  return `${window.location.protocol}//${window.location.hostname}:8000${path}`
}
