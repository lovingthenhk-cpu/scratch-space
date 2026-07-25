/*
 * Faster systematic sweep for the generalized Collatz map
 *   T_q(n) = n/2       if n even
 *          = q*n + 1   if n odd
 * over odd n = 1, 3, 5, ..., LIMIT, looking for ALL distinct nontrivial
 * cycles reachable in that range (continuing 2026-07-25's sweep_cycles.c).
 *
 * WHY A NEW VERSION: the 2026-07-25 sweep_cycles.c cleared its whole
 * per-walk hash table (HCAP=80000 slots) with memset() at the start of
 * EVERY single walk() call. That's ~1.28MB touched per odd n, dominating
 * runtime regardless of how short the actual trajectory is (most q>=5
 * trajectories diverge and exit after only a few dozen steps). That made
 * sweeping past a few million infeasible in reasonable time.
 *
 * FIX: replace the per-call memset with an "epoch"/version-tagged hash
 * table. The table persists across calls; each slot remembers which walk
 * (global counter `epoch`) last wrote it. A slot is treated as empty if
 * its stored epoch != current epoch, so "clearing" the table for a new
 * walk is O(1) (just increment epoch) instead of O(table size). This
 * turns the per-n cost into O(actual trajectory length) as it should be,
 * which is a >100x speedup for the divergent-heavy q>=5 regime, letting
 * us push the sweep limit from 3*10^6 to 10^8+ in the same wall-clock
 * budget.
 *
 * Correctness check: this file must reproduce, byte-for-byte, the same
 * two nontrivial q=5 10-cycles found by sweep_cycles.c over odd n<=3*10^6:
 *   {13,66,33,166,83,416,208,104,52,26}
 *   {17,86,43,216,108,54,27,136,68,34}
 * (verified in v2_verify.log before any larger run was trusted.)
 */
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>

#define MAX_STEPS 20000
#define DIVERGE_THRESHOLD ((uint64_t)1e17)
#define DIVERGE_MIN_STEPS 30

/* epoch-tagged open-addressing hash table slot */
typedef struct { uint64_t key; int32_t idx; uint32_t epoch; } Slot;

#define HCAP (1u << 20)  /* 1M slots, fixed regardless of MAX_STEPS; plenty
                            for the handful-to-few-hundred distinct values
                            any single walk touches before diverging or
                            closing a cycle. */
static Slot table[HCAP];
static uint32_t cur_epoch = 0;

/* returns previous idx if key already present in the CURRENT epoch,
 * else inserts (key,idx) tagged with cur_epoch and returns -1. */
static int htable_find_or_insert(uint64_t key, int idx) {
    uint64_t h = (key * 11400714819323198485ULL) >> 32;
    uint32_t i = (uint32_t)(h & (HCAP - 1));
    while (1) {
        if (table[i].epoch != cur_epoch) {
            table[i].key = key; table[i].idx = idx; table[i].epoch = cur_epoch;
            return -1;
        }
        if (table[i].key == key) return table[i].idx;
        i = (i + 1) & (HCAP - 1);
    }
}

typedef enum { REACHED_ONE, REACHED_OTHER_CYCLE, DIVERGED, INCONCLUSIVE } Outcome;

static uint64_t path_vals[MAX_STEPS];

#define MAX_CYCLES 64
#define MAX_CYCLE_LEN 256
static uint64_t known_cycles[MAX_CYCLES][MAX_CYCLE_LEN];
static int known_cycle_lens[MAX_CYCLES];
static uint64_t known_cycle_first_n[MAX_CYCLES];
static int n_known_cycles = 0;

static int cmp_u64(const void *a, const void *b) {
    uint64_t x = *(const uint64_t*)a, y = *(const uint64_t*)b;
    return (x > y) - (x < y);
}

static int record_cycle_if_new(uint64_t *elems, int len, uint64_t witness_n) {
    if (len > MAX_CYCLE_LEN) return -1;
    uint64_t sorted[MAX_CYCLE_LEN];
    memcpy(sorted, elems, len * sizeof(uint64_t));
    qsort(sorted, len, sizeof(uint64_t), cmp_u64);
    for (int c = 0; c < n_known_cycles; c++) {
        if (known_cycle_lens[c] != len) continue;
        if (memcmp(known_cycles[c], sorted, len * sizeof(uint64_t)) == 0) return c;
    }
    if (n_known_cycles < MAX_CYCLES) {
        memcpy(known_cycles[n_known_cycles], sorted, len * sizeof(uint64_t));
        known_cycle_lens[n_known_cycles] = len;
        known_cycle_first_n[n_known_cycles] = witness_n;
        n_known_cycles++;
        return n_known_cycles - 1;
    }
    return -1;
}

static Outcome walk(uint64_t n0, uint64_t q, int *out_steps) {
    cur_epoch++;
    if (cur_epoch == 0) { /* wrapped after 2^32 calls; force a real clear (never happens in practice) */
        memset(table, 0, sizeof(table));
        cur_epoch = 1;
    }
    uint64_t n = n0;
    for (int step = 0; step < MAX_STEPS; step++) {
        if (n == 1) { *out_steps = step; return REACHED_ONE; }
        int prev = htable_find_or_insert(n, step);
        if (prev != -1) {
            int clen = step - prev;
            record_cycle_if_new(&path_vals[prev], clen, n0);
            *out_steps = step;
            return REACHED_OTHER_CYCLE;
        }
        path_vals[step] = n;
        if (n % 2 == 0) { n = n / 2; }
        else {
            if (n > (UINT64_MAX - 1) / q) {
                /* BUGFIX (2026-07-26): this used to be
                 *   return (step > DIVERGE_MIN_STEPS) ? DIVERGED : INCONCLUSIVE;
                 * which silently misclassified genuine divergence as
                 * INCONCLUSIVE whenever the overflow guard tripped at
                 * step <= DIVERGE_MIN_STEPS (found: exactly step==30 for a
                 * whole arithmetic progression of q=13 starting values,
                 * spaced 2^16 apart -- see 2026-07-26/REPORT.md). The
                 * overflow guard threshold (UINT64_MAX-1)/q is, for every
                 * q we use (5..13), always far above DIVERGE_THRESHOLD
                 * (1e17), so tripping it already implies n blew past the
                 * ordinary threshold a step or two earlier; there is no
                 * scenario in this sweep (n0 << 1e17) where the guard
                 * fires this early on a trajectory that isn't genuinely
                 * diverging. So: always DIVERGED here, unconditionally. */
                *out_steps = step;
                return DIVERGED;
            }
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
    uint64_t start = (argc > 3) ? strtoull(argv[3], NULL, 10) : 1ULL;
    if (start % 2 == 0) start++; /* keep odd */

    long cnt_one = 0, cnt_cycle = 0, cnt_div = 0, cnt_inconc = 0;
    uint64_t first_other_cycle_n = 0;

    for (uint64_t n = start; n <= limit; n += 2) {
        int steps;
        Outcome o = walk(n, q, &steps);
        switch (o) {
            case REACHED_ONE: cnt_one++; break;
            case REACHED_OTHER_CYCLE:
                cnt_cycle++;
                if (!first_other_cycle_n) first_other_cycle_n = n;
                break;
            case DIVERGED: cnt_div++; break;
            case INCONCLUSIVE: cnt_inconc++;
                fprintf(stderr, "INCONCLUSIVE at n=%llu (q=%llu) -- MAX_STEPS too small?\n",
                        (unsigned long long)n, (unsigned long long)q);
                break;
        }
    }

    printf("q=%llu sweep over odd n in [%llu,%llu]:\n", (unsigned long long)q,
           (unsigned long long)start, (unsigned long long)limit);
    printf("  reached_one=%ld  reached_other_cycle=%ld  diverged=%ld  inconclusive=%ld\n",
           cnt_one, cnt_cycle, cnt_div, cnt_inconc);
    printf("  distinct nontrivial cycles found: %d\n", n_known_cycles);
    for (int c = 0; c < n_known_cycles; c++) {
        printf("    cycle #%d (len=%d, first witnessed at n=%llu): ", c, known_cycle_lens[c],
               (unsigned long long)known_cycle_first_n[c]);
        for (int i = 0; i < known_cycle_lens[c]; i++) printf("%llu ", (unsigned long long)known_cycles[c][i]);
        printf("\n");
    }
    return 0;
}
