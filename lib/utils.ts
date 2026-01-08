import { type ClassValue, clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function slugify(text: string): string {
  return text
    .toString()
    .toLowerCase()
    .trim()
    .replace(/\s+/g, '-')     // Replace spaces with -
    .replace(/[^\w\-]+/g, '') // Remove all non-word chars
    .replace(/\-\-+/g, '-');  // Replace multiple - with single -
}

export function unslugify(slug: string): string {
  // Rough reverse, usually better to store slug in DB or query by partial match, 
  // but for this exercise we assume slug ~ subject_name
  return slug.split('-').map(word => word.charAt(0).toUpperCase() + word.slice(1)).join(' ');
}

export function formatDate(dateString: string): string {
  return new Date(dateString).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}

export function getScoreColor(score: number) {
  if (score >= 70) return 'text-green-400 border-green-400';
  if (score >= 40) return 'text-yellow-400 border-yellow-400';
  return 'text-red-400 border-red-400';
}
