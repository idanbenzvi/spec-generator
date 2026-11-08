// STUB (milestone M3): static output, React islands for the explorer and comparator.
import { defineConfig } from 'astro/config';
import react from '@astrojs/react';
export default defineConfig({ output: 'static', integrations: [react()] });
