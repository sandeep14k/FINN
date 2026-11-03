export const companyNames: Record<string, string> = {
  RELIANCE: 'Reliance Industries', INFY: 'Infosys', ITC: 'ITC', LT: 'Larsen & Toubro', ICICIBANK: 'ICICI Bank', BHARTIARTL: 'Bharti Airtel', TRENT: 'Trent', POLYCAB: 'Polycab India', DIXON: 'Dixon Technologies', INDHOTEL: 'Indian Hotels', CUMMINSIND: 'Cummins India', CDSL: 'CDSL', TATASTEEL: 'Tata Steel', ONGC: 'ONGC', NEULANDLAB: 'Neuland Laboratories', PRAJIND: 'Praj Industries', JYOTHYLAB: 'Jyothy Labs', RKFORGE: 'Ramkrishna Forgings', KPITTECH: 'KPIT Technologies', ETERNAL: 'Eternal', LAURUSLABS: 'Laurus Labs', TCS: 'Tata Consultancy Services', HCLTECH: 'HCL Technologies',
};
export const categories = ['results', 'management_change', 'M&A', 'litigation', 'credit_rating', 'capex', 'fund_raise', 'earnings_call', 'dividend', 'pledging'];
export const defaults = { price: 3, volume: 2.5, categories };
export const titleCase = (value: string) => value === 'M&A' ? value : value.replaceAll('_', ' ').replace(/\b\w/g, char => char.toUpperCase());
export const dateLabel = (value: string, year = false) => new Date(value).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', ...(year ? { year: 'numeric' } : {}), timeZone: 'Asia/Kolkata' });
export const money = (value: number | null | undefined) => value == null ? '—' : `₹${value.toLocaleString('en-IN', { maximumFractionDigits: 2 })}`;
export const percent = (value: number | null | undefined) => value == null ? '—' : `${value > 0 ? '+' : ''}${value.toFixed(2)}%`;
export async function getJSON(url: string) {
  const response = await fetch(url, { cache: 'no-store' });
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || `Could not load data (${response.status}).`);
  return result;
}
