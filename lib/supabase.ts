import { createClient } from '@supabase/supabase-js';
import { SUPABASE_URL, SUPABASE_ANON_KEY } from '../constants';

// Fallback to placeholder to prevent build-time crash if env vars are missing.
// The app will function but API calls will fail at runtime if keys are invalid, which is better than a build failure.
const url = SUPABASE_URL || 'https://placeholder.supabase.co';
const key = SUPABASE_ANON_KEY || 'placeholder';

export const supabase = createClient(url, key);