interface Body {
  json(): Promise<unknown>;
}

interface JSON {
  parse(
    text: string,
    reviver?: {
      revive(this: unknown, key: string, value: unknown): unknown;
    }["revive"],
  ): unknown;
}

interface ArrayConstructor {
  isArray(arg: unknown): arg is readonly unknown[];
}
