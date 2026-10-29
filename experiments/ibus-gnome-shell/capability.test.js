import GLib from 'gi://GLib';
import {checkCapability} from './capability.js';
const token = 'a'.repeat(64);
if (!checkCapability(token)) throw new Error('valid token rejected');
if (checkCapability('b'.repeat(64))) throw new Error('invalid token accepted');
print('descriptor capability checks passed');
