// Typed contracts for the local HTTP API. Business and registry values remain source data.
interface CompanyRow { id:number; title:string; address?:string; postal?:string; city?:string; country?:string; phone?:string; website?:string; providers?:string }
interface CompanyPage { total:number; rows:CompanyRow[] }
interface CompanyDetails extends CompanyRow { [field:string]: unknown; sources?:{provider:string;url:string;updated:string}[]; alternate_values?:{field:string;value:string;provider:string;observed_at:string}[] }
interface CompanyHistory { changed_at:string;provider:string;changes:Record<string,{before:unknown;after:unknown}> }
interface DashboardStats { total:number; cities:number; phones:number; websites:number; top_cities:{city:string;n:number}[] }
interface BotStatus { status:string; phase?:string; snapshot_id?:string; projected?:number; projection_total?:number; update_available?:string; local_snapshot?:string; reused?:number; repaired?:number; kind?:string; page:number;last:number;processed:number;added:number;skipped:number;errors:number;logs:string[] }
interface SourceInfo { label:string;provider:string;n:number }
interface RegistryRun { snapshot:string;complete:number|boolean }
interface RegistryCategory { snapshot:string;category:string;rows:number;total:number|null;done:number|boolean }
interface RegistrySummary { configured:boolean;authorized:boolean;runs:RegistryRun[];categories:RegistryCategory[] }
interface RegistryPage { total:number;rows:Record<string,unknown>[] }
interface RegistryDiff { before:string;after:string;categories:{category:string;comparable:boolean;added:number;removed:number;affected_subjects:number}[] }
interface JobSummary { update_sync:{enabled:boolean|number;last_version:string}; schedule:{enabled:boolean|number;hour:number}; jobs:{id:number;kind:string;state:string;created:string;finished?:string;attempts?:number;next_run?:number}[] }
