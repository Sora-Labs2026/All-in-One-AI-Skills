import { helper } from './lib/util';
import * as lib from './lib';
import {
  formatDate,
  parseDate,
} from "@/lib/dates";
import type { Config } from './types';
import React from 'react';
import fs from 'node:fs';
import path from 'path';
import { thing } from '@scope/pkg/sub';
// import { ghost } from './ghost';
/* import { ghost2 } from './ghost2'; */
import { esm } from './lib/esm.js';
import './styles.css';

export const VERSION = '1.0.0';

export function start(config: Config) {
  const later = import('./lazy');
  return [helper(config), lib.name, formatDate(), parseDate(), esm, thing, React, fs, path, later];
}

export default class App {}

export interface Options { verbose: boolean }

export type Mode = 'a' | 'b';

const localHelper = (x: number) => x + 1;
