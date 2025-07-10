import { writable, derived, get } from 'svelte/store';
import { offlineMode } from './main';
import { apiFetch } from '$lib/utils/api';

// API calls now use environment-aware utility functions

// Types
export interface Contestant {
	id: string;
	number: number;
	name: string;
	nickname: string;
	age: number;
	has_photos: boolean;
	has_embedding: boolean;
	photo_url: string | null;
}

// Stores
export const contestants = writable<Contestant[]>([]);
export const loading = writable(false);
export const error = writable<string | null>(null);
export const searchQuery = writable('');
export const selectedContestant = writable<Contestant | null>(null);

// Derived stores
export const contestantCount = derived(contestants, ($contestants) => $contestants ? $contestants.length : 0);

export const contestantsWithEmbeddings = derived(
	contestants, 
	($contestants) => $contestants.filter(c => c.has_embedding)
);

export const filteredContestants = derived(
	[contestants, searchQuery],
	([$contestants, $query]) => {
		if (!$query) return $contestants;
		
		const query = $query.toLowerCase();
		return $contestants.filter(c => 
			c.name.toLowerCase().includes(query) || 
			c.nickname.toLowerCase().includes(query)
		);
	}
);

export const contestantsByLetter = derived(
	filteredContestants,
	($filtered) => {
		const grouped: Record<string, Contestant[]> = {};
		
		$filtered.forEach(contestant => {
			const letter = contestant.nickname.charAt(0).toUpperCase();
			if (!grouped[letter]) {
				grouped[letter] = [];
			}
			grouped[letter].push(contestant);
		});
		
		// Sort each group
		Object.keys(grouped).forEach(letter => {
			grouped[letter].sort((a, b) => a.nickname.localeCompare(b.nickname));
		});
		
		return grouped;
	}
);

// Store instance for backward compatibility
export const contestantsStore = {
	subscribe: contestants.subscribe,
	set: contestants.set,
	update: contestants.update,
	
	// Expose contestants as property for component compatibility
	contestants,
	
	async loadContestants() {
		loading.set(true);
		error.set(null);
		
		try {
			// Try to load from live API first
			const data = await apiFetch('/api/contestants');
			contestants.set(data);
		} catch (err) {
			console.warn('Failed to load from API, checking offline mode:', err);
			
			// Check if in offline mode
			if (get(offlineMode)) {
				// Return mock contestants data as fallback
				const mockContestants: Contestant[] = [
					{
						id: '1',
						number: 1,
						name: '蘇雅琳',
						nickname: 'Ivy So',
						age: 20,
						has_photos: true,
						has_embedding: true,
						photo_url: '/source/photo/contestants/1/1-1.jpg'
					},
					{
						id: '2',
						number: 2,
						name: '黃雅慧',
						nickname: '咖喱',
						age: 27,
						has_photos: true,
						has_embedding: true,
						photo_url: '/source/photo/contestants/2/2-1.jpg'
					},
					{
						id: '3',
						number: 3,
						name: '邱彥筒',
						nickname: 'Marf',
						age: 19,
						has_photos: true,
						has_embedding: true,
						photo_url: '/source/photo/contestants/3/3-1.jpg'
					},
					{
						id: '96',
						number: 96,
						name: '郭嘉盈',
						nickname: '3 妹',
						age: 26,
						has_photos: true,
						has_embedding: true,
						photo_url: '/source/photo/contestants/96/96-1.jpg'
					}
				];
				contestants.set(mockContestants);
			} else {
				error.set(err instanceof Error ? err.message : 'Failed to load contestants');
			}
		} finally {
			loading.set(false);
		}
	},

	selectContestant(contestant: Contestant) {
		selectedContestant.set(contestant);
	},

	clearSelection() {
		selectedContestant.set(null);
	},

	setSearchQuery(query: string) {
		searchQuery.set(query);
	},

	clearSearch() {
		searchQuery.set('');
	},

	clearError() {
		error.set(null);
	}
};
