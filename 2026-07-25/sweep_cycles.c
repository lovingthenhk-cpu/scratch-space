/*
 * Systematic (non-random) sweep for the generalized Collatz map
 * T_q(n) = n/2 (n even), q*n+1 (n odd), over small odd n = 1,3,5,...,LIMIT,
 * looking for ALL distinct bounded outcomes (reaches 1, or falls into some
 * other finite cycle) in that range, and de-duplicating the cycles found.
 *
 * This complements generalized_qn1.c's random-sampling-over-large-magnitudes
 * approach: here we exhaustively sweep small n, which is a natural place to
 * look for the "known" nontrivial cycles (in the literature on generalized
 * 3x+1 maps these are usually small). Any nontrivial cycle found is printed
 * with its full element list (not just the minimum element) sorted, and
 * de-duplicated by its frozenset of member values so revisits from a
 * different entry point don't get double-counted.
 */
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>

#define MAX_STEPS 20000
#define DIVERGE_THRESHOLD ((uint64_t)1e17)
#define DIVERGE_MIN_STEPS 30

typedef struct { uint64_t key; int32_t idx; } Slot;

static int htable_find_or_insert(Slot *table, int cap, uint64_t key, int idx) {
    uint64_t h = (key * 11400714819323198485ULL) >> 32;
    int i = (int)(h % (uint64_t)cap);
    while (1) {
        if (table[i].idx == -1) { table[i].key = key; table[i].idx = idx; return -1; }
        if (table[i].key == key) return table[i].idx;
        i++; if (i == cap) i = 0;
    }
}

typedef enum { REACHED_ONE, REACHED_OTHER_CYCLE, DIVERGED, INCONCLUSIVE } Outcome;

#define HCAP (MAX_STEPS * 4)
static Slot table[HCAP];
static uint64_t path_vals[MAX_STEPS];

/* stores up to MAX_CYCLES distinct nontrivial cycles found, identified by
 * (sorted element list). very small cycles expected (<=100 elements say),
 * so linear scan for de-dup is fine. */
#define MAX_CYCLES 64
#define MAX_CYCLE_LEN 256
static uint64_t known_cycles[MAX_CYCLES][MAX_CYCLE_LEN];
static int known_cycle_lens[MAX_CYCLES];
static int n_known_cycles = 0;

static int cmp_u64(const void *a, const void *b) {
    uint64_t x = *(const uint64_t*)a, y = *(const uint64_t*)b;
    return (x > y) - (x < y);
}

static int record_cycle_if_new(uint64_t *elems, int len) {
    if (len > MAX_CYCLE_LEN) return -1; /* too long to bother, skip */
    uint64_t sorted[MAX_CYCLE_LEN];
    memcpy(sorted, elems, len * sizeof(uint64_t));
    qsort(sorted, len, sizeof(uint64_t), cmp_u64);
    for (int c = 0; c < n_known_cycles; c++) {
        if (known_cycle_lens[c] != len) continue;
        if (memcmp(known_cycles[c], sorted, len * sizeof(uint64_t)) == 0) return c; /* already known */
    }
    if (n_known_cycles < MAX_CYCLES) {
        memcpy(known_cycles[n_known_cycles], sorted, len * sizeof(uint64_t));
        known_cycle_lens[n_known_cycles] = len;
        n_known_cycles++;
        return n_known_cycles - 1;
    }
    return -1;
}

static Outcome walk(uint64_t n0, uint64_t q, int *out_steps) {
    memset(table, 0xFF, HCAP * sizeof(Slot));
    uint64_t n = n0;
    for (int step = 0; step < MAX_STEPS; step++) {
        if (n == 1) { *out_steps = step; return REACHED_ONE; }
        int prev = htable_find_or_insert(table, HCAP, n, step);
        if (prev != -1) {
            int clen = step - prev;
            record_cycle_if_new(&path_vals[prev], clen);
            *out_steps = step;
            return REACHED_OTHER_CYCLE;
        }
        path_vals[step] = n;
        if (n % 2 == 0) { n = n / 2; }
        else {
            if (n > (UINT64_MAX - 1) / q) { *out_steps = step; return (step > DIVERGE_MIN_STEPS) ? DIVERGED : INCONCLUSIVE; }
            n = q * n + 1;
        }
        if (n > DIVERGE_THRESHOLD && step > DIVERGE_MIN_STEPS) { *out_steps = step + 1; return DIVERGED; }
    }
    *out_steps = MAX_STEPS;
    return INCONCLUSIVE;
}

int main(int argc, char **argv) {
    uint64_t q = (argc > 1) ? strtoull(argv[1], NULL, 10) : 7;
    uint64_t limit = (argc > 2) ? strtoull(argv[2], NULL, 10) : 2000000ULL;

    long cnt_one = 0, cnt_cycle = 0, cnt_div = 0, cnt_inconc = 0;
    uint64_t first_other_cycle_n = 0;

    for (uint64_t n = 1; n <= limit; n += 2) {
        int steps;
        Outcome o = walk(n, q, &steps);
        switch (o) {
            case REACHED_ONE: cnt_one++; break;
            case REACHED_OTHER_CYCLE:
                cnt_cycle++;
                if (!first_other_cycle_n) first_other_cycle_n = n;
                break;
            case DIVERGED: cnt_div++; break;
            case INCONCLUSIVE: cnt_inconc++; break;
        }
    }

    printf("q=%llu sweep over odd n in [1,%llu]:\n", (unsigned long long)q, (unsigned long long)limit);
    printf("  reached_one=%ld  reached_other_cycle=%ld  diverged=%ld  inconclusive=%ld\n",
           cnt_one, cnt_cycle, cnt_div, cnt_inconc);
    printf("  distinct nontrivial cycles found: %d\n", n_known_cycles);
    for (int c = 0; c < n_known_cycles; c++) {
        printf("    cycle #%d (len=%d): ", c, known_cycle_lens[c]);
        for (int i = 0; i < known_cycle_lens[c]; i++) printf("%llu ", (unsigned long long)known_cycles[c][i]);
        printf("\n");
    }
    return 0;
}
