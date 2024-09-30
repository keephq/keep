export type InterfaceToType<T> = {
  [K in keyof T]: T[K];
};
