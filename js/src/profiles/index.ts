/** Provider profiles: data files that say what each TTS model accepts.
 *
 * The YAML files live in the repository's `spec/profiles`. The build step turns
 * them into `data.ts` so the package needs no YAML parser at runtime. Each
 * profile states the intent renderings, the request limit, the escaping rules
 * and whether unknown bracket tags pass through.
 */

import { PROFILE_DATA } from "./data.js";

export interface Profile {
  id: string;
  provider: string;
  models: string[];
  /** plain | ssml */
  syntax: string;
  /** none | xml */
  escape: string;
  /** chars | bytes */
  limitUnit: string;
  limitMax: number | null;
  limitPerModel: Record<string, number>;
  intents: Record<string, Record<string, unknown>>;
  audioTags: boolean;
  /** pls | google | none: how a lexicon is uploaded to this provider */
  lexiconFormat: string;
  lexiconAlphabet: string;
  default: boolean;
  notes: string;
  sources: string[];
  verified: string;
  raw: Record<string, unknown>;
  limitFor(model?: string | null): number | null;
}

type Raw = Record<string, unknown>;

function fromDict(data: Raw): Profile {
  const limit = (data.limit ?? {}) as Raw;
  const lexicon = (data.lexicon ?? {}) as Raw;
  const profile: Profile = {
    id: String(data.id),
    provider: String(data.provider),
    models: ((data.models as string[] | undefined) ?? []).map(String),
    syntax: (data.syntax as string | undefined) ?? "plain",
    escape: (data.escape as string | undefined) ?? "none",
    limitUnit: (limit.unit as string | undefined) ?? "chars",
    limitMax: (limit.max as number | null | undefined) ?? null,
    limitPerModel: { ...((limit.per_model as Record<string, number> | undefined) ?? {}) },
    intents: { ...((data.intents as Record<string, Record<string, unknown>> | undefined) ?? {}) },
    audioTags: Boolean(data.audio_tags ?? false),
    lexiconFormat: String(lexicon.format ?? "none"),
    lexiconAlphabet: String(lexicon.alphabet ?? "ipa"),
    default: Boolean(data.default ?? false),
    notes: (data.notes as string | undefined) ?? "",
    sources: ((data.sources as string[] | undefined) ?? []).map(String),
    verified: String(data.verified ?? ""),
    raw: data,
    limitFor(model?: string | null): number | null {
      if (model && model in this.limitPerModel) return this.limitPerModel[model];
      return this.limitMax;
    },
  };
  return profile;
}

let cache: Profile[] | null = null;

function all(): Profile[] {
  if (!cache) cache = (PROFILE_DATA as Raw[]).map(fromDict);
  return cache;
}

export function listProfiles(): Profile[] {
  return [...all()];
}

export function loadProfile(profileId: string): Profile {
  for (const p of all()) if (p.id === profileId) return p;
  throw new Error(`unknown profile ${JSON.stringify(profileId)}; known: ${all().map((p) => p.id).join(", ")}`);
}

/** Pick the profile for a provider and model. No provider = the `plain` profile. */
export function resolveProfile(provider?: string | null, model?: string | null): Profile {
  if (!provider && !model) return loadProfile("plain");
  const matches = all().filter((p) => !provider || p.provider === provider);
  if (model) {
    for (const p of matches) if (p.models.includes(model)) return p;
    if (!provider) throw new Error(`no profile lists model ${JSON.stringify(model)}`);
  }
  for (const p of matches) if (p.default) return p;
  if (matches.length) return matches[0];
  const known = [...new Set(all().map((p) => p.provider))].sort();
  throw new Error(`no profile for provider ${JSON.stringify(provider)}; known providers: ${known.join(", ")}`);
}
