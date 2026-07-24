/*
 * Generalized Collatz map experiment: T_q(n) = n/2 if n even, q*n+1 if n odd,
 * for odd q >= 3.
 *
 * Motivation (see PROGRESS.md item 3 from 2026-07-24): the standard
 * "equilibrium heuristic" for the ordinary Collatz map (q=3) says a full
 * odd-step-then-halvings cycle multiplies a typical n by q/4 on average
 * (odd step multiplies by ~q, and the run of halvings that follows an odd
 * step has an average length of 2, i.e. divides by ~4 on average, since the
 * number of trailing halvings after n -> qn+1 is geometrically distributed
 * with mean 2 when qn+1's parity bits are "random").
 *
 *   q=3:  net factor 3/4 = 0.75   < 1  => heuristic predicts a.e. convergence
 *   q=5:  net factor 5/4 = 1.25   > 1  => heuristic predicts a.e. divergence
 *   q=7:  net factor 7/4 = 1.75   > 1  => heuristic predicts a.e. divergence
 *   q=9:  net factor 9/4 = 2.25   > 1  => heuristic predicts a.e. divergence
 *
 * This is the standard reason q=3 is the "interesting" borderline case:
 * it's the unique odd q>=3 with q/4 < 1. This program does NOT try to prove
 * anything -- it empirically samples many random large starting values for
 * several q, walks the trajectory with overflow-safe uint64 arithmetic, and
 * classifies each one as:
 *   - "reached 1"          (fell into the cycle containing 1)
 *   - "reached small cycle" (fell into a *different* bounded cycle -- these
 *                             exist for many q, e.g. for q=5 there's a known
 *                             6-term cycle {1,3,16,8,4,2} containing 1 itself,
 *                             but other q can have cycles that do not pass
 *                             through 1 at all)
 *   - "diverged"            (grew past a large threshold after enough steps
 *                             that it's very unlikely to be a transient spike
 *                             -- consistent with the heuristic for q>=5)
 *   - "inconclusive"        (hit the step budget without doing either --
 *                             can happen near the divergence/step-cap boundary)
 *
 * Cycle detection: we keep the visited path (n, step_index) in an open
 * addressing hash table so we can detect "we've seen this value before in
 * this trajectory" in O(1) amortized, and report the cycle length + a
 * representative element (the smallest value in the cycle) when found.
 */
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <time.h>

#define MAX_STEPS 20000
#define DIVERGE_THRESHOLD ((uint64_t)1e17)   /* well below UINT64_MAX ~1.8e19 */
#define DIVERGE_MIN_STEPS 30                 /* don't call it "diverged" on a trivial one-step jump
                                               * from an already-huge n0; for q>=5 growth is genuinely
                                               * fast (see header comment), so a small gate suffices --
                                               * this is not the q=3 case where transient spikes are
                                               * common despite overall contraction. */

/* simple open-addressing hash set: value -> step index, for cycle detection */
typedef struct { uint64_t key; int32_t idx; } Slot;

static int htable_find_or_insert(Slot *table, int cap, uint64_t key, int idx) {
    uint64_t h = (key * 11400714819323198485ULL) >> 32; /* fibonacci hashing, top bits */
    int i = (int)(h % (uint64_t)cap);
    while (1) {
        if (table[i].idx == -1) { table[i].key = key; table[i].idx = idx; return -1; /* new */ }
        if (table[i].key == key) return table[i].idx; /* found: return earlier index */
        i++; if (i == cap) i = 0;
    }
}

typedef enum { REACHED_ONE, REACHED_OTHER_CYCLE, DIVERGED, INCONCLUSIVE, SKIPPED_OVERFLOW } Outcome;

typedef struct {
    Outcome outcome;
    uint64_t n0;
    int steps;
    uint64_t cycle_min_elem; /* only for REACHED_OTHER_CYCLE */
    int cycle_len;
} Result;

static int HCAP;
static Slot *table;
static uint64_t *path_vals;

static Result walk(uint64_t n0, uint64_t q) {
    Result r; r.n0 = n0; r.cycle_len = 0; r.cycle_min_elem = 0;
    memset(table, 0xFF, HCAP * sizeof(Slot)); /* idx=-1 means empty (0xFFFFFFFF as int32 is -1) */

    uint64_t n = n0;
    for (int step = 0; step < MAX_STEPS; step++) {
        if (n == 1) { r.outcome = REACHED_ONE; r.steps = step; return r; }

        int prev = htable_find_or_insert(table, HCAP, n, step);
        if (prev != -1) {
            /* cycle found: n reappears; cycle length = step - prev */
            int clen = step - prev;
            uint64_t minv = n;
            for (int k = prev; k < step; k++) if (path_vals[k] < minv) minv = path_vals[k];
            r.outcome = REACHED_OTHER_CYCLE;
            r.steps = step;
            r.cycle_len = clen;
            r.cycle_min_elem = minv;
            return r;
        }
        path_vals[step] = n;

        if (n % 2 == 0) {
            n = n / 2;
        } else {
            /* overflow guard: hitting the uint64 ceiling from a modest n0 within
             * a bounded step budget is itself strong evidence of unbounded
             * growth for q>=5 (see header), so we classify it as DIVERGED
             * rather than as an inconclusive/skipped case. */
            if (n > (UINT64_MAX - 1) / q) {
                r.outcome = (step > DIVERGE_MIN_STEPS) ? DIVERGED : SKIPPED_OVERFLOW;
                r.steps = step;
                return r;
            }
            n = q * n + 1;
        }

        if (n > DIVERGE_THRESHOLD && step > DIVERGE_MIN_STEPS) {
            r.outcome = DIVERGED; r.steps = step + 1; return r;
        }
    }
    r.outcome = INCONCLUSIVE; r.steps = MAX_STEPS;
    return r;
}

int main(int argc, char **argv) {
    uint64_t q = (argc > 1) ? strtoull(argv[1], NULL, 10) : 5;
    int n_samples = (argc > 2) ? atoi(argv[2]) : 20000;
    unsigned int seed = (argc > 3) ? (unsigned int)strtoul(argv[3], NULL, 10) : 42u;
    const char *outcsv = (argc > 4) ? argv[4] : "qn1_samples.csv";

    if (q % 2 == 0 || q < 3) { fprintf(stderr, "q must be odd and >=3\n"); return 1; }

    HCAP = 1; while (HCAP < MAX_STEPS * 4) HCAP <<= 1;
    table = malloc(HCAP * sizeof(Slot));
    path_vals = malloc(MAX_STEPS * sizeof(uint64_t));

    srand(seed);
    FILE *f = fopen(outcsv, "w");
    fprintf(f, "q,n0,outcome,steps,cycle_len,cycle_min_elem\n");

    long cnt_one = 0, cnt_other_cycle = 0, cnt_diverged = 0, cnt_inconclusive = 0, cnt_overflow_skip = 0;

    for (int s = 0; s < n_samples; s++) {
        int decade = 4 + (rand() % 12); /* 10^4 .. 10^15 */
        uint64_t lo = 1; for (int i = 0; i < decade; i++) lo *= 10;
        uint64_t hi = lo * 10;
        uint64_t span = hi - lo;
        uint64_t r64 = ((uint64_t)rand() << 32) ^ ((uint64_t)rand() << 16) ^ (uint64_t)rand();
        uint64_t n0 = lo + (r64 % span);
        if (n0 % 2 == 0) n0 += 1;

        Result res = walk(n0, q);
        const char *oname;
        switch (res.outcome) {
            case REACHED_ONE: oname = "reached_one"; cnt_one++; break;
            case REACHED_OTHER_CYCLE: oname = "reached_other_cycle"; cnt_other_cycle++; break;
            case DIVERGED: oname = "diverged"; cnt_diverged++; break;
            case INCONCLUSIVE: oname = "inconclusive"; cnt_inconclusive++; break;
            default: oname = "overflow_skip"; cnt_overflow_skip++; break;
        }
        fprintf(f, "%llu,%llu,%s,%d,%d,%llu\n",
                (unsigned long long)q, (unsigned long long)n0, oname, res.steps,
                res.cycle_len, (unsigned long long)res.cycle_min_elem);
    }
    fclose(f);

    fprintf(stderr, "q=%llu, n_samples=%d\n", (unsigned long long)q, n_samples);
    fprintf(stderr, "  reached_one:          %ld (%.2f%%)\n", cnt_one, 100.0*cnt_one/n_samples);
    fprintf(stderr, "  reached_other_cycle:  %ld (%.2f%%)\n", cnt_other_cycle, 100.0*cnt_other_cycle/n_samples);
    fprintf(stderr, "  diverged:             %ld (%.2f%%)\n", cnt_diverged, 100.0*cnt_diverged/n_samples);
    fprintf(stderr, "  inconclusive:         %ld (%.2f%%)\n", cnt_inconclusive, 100.0*cnt_inconclusive/n_samples);
    fprintf(stderr, "  overflow_skip:        %ld (%.2f%%)\n", cnt_overflow_skip, 100.0*cnt_overflow_skip/n_samples);

    free(table); free(path_vals);
    return 0;
}
