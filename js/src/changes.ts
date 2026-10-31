/** The audit trail: one Change per rewrite the pipeline made. */

export interface Change {
  stage: string;
  /** Dotted and stable, e.g. `clean.markdown.heading`. */
  rule: string;
  before: string;
  after: string;
  note: string;
}

/** Collects Changes; stages call `add` whenever they rewrite something. */
export class Recorder {
  changes: Change[] = [];

  add(stage: string, rule: string, before: string, after: string, note = ""): void {
    if (before === after) return;
    this.changes.push({ stage, rule, before, after, note });
  }
}
