/*
 * Collatz (3x+1) conjecture: bulk verification + record tracking.
 *
 * For every n in [1, N) we compute the "total stopping time" (number of
 * steps of the map
 *     n -> n/2        if n even
 *     n -> 3n+1       if n odd
 * required to reach 1), and the "peak value" (max value attained along the
 * trajectory). We use a memoization table for n < MEMO_N so that once a
 * trajectory falls below MEMO_N we can look up the remaining step count in
 * O(1) instead of re-walking it. Numbers below MEMO_N get their memo entry
 * filled in lazily (path compression) the first time they are visited.
 *
 * We track:
 *   - whether every n in [1,N) reaches 1 (a crash / infinite loop guard
 *     would indicate a counterexample, which we do not expect to find, but
 *     the code does not assume convergence going in)
 *   - "glide" (total stopping time) records: n whose step count exceeds
 *     every step count seen for smaller n
 *   - "peak" records: n whose max trajectory value (or max value / n ratio)
 *     exceeds every one seen for smaller n
 *
 * Output: CSV files of both record streams, plus summary stats on stderr.
 */
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <math.h>

#ifndef MEMO_N
#define MEMO_N 20000000ULL   /* memoize step counts for n < 2e7 */
#endif

static uint16_t *memo;                 /* memo[n] = total stopping time of n, 0xFFFF = unknown */
#define SENTINEL 0xFFFFu

/* Loop-detection guard: max path length we allow before declaring failure.
 * (Chosen generously; observed stopping times for n up to 1e9 are well
 * under a few thousand steps, but we allow much more headroom.) */
#define MAX_STEPS 100000

typedef struct { uint64_t n; uint32_t at; } PathEntry;

static uint32_t stopping_time(uint64_t n0, uint64_t *peak_out) {
    static PathEntry path[MAX_STEPS];
    int pathlen = 0;
    uint64_t n = n0;
    uint64_t peak = n0;
    uint32_t steps = 0;

    while (1) {
        if (n == 1) {
            uint32_t total = steps;
            for (int i = 0; i < pathlen; i++) {
                uint64_t v = path[i].n;
                if (v < MEMO_N) memo[v] = (uint16_t)(total - path[i].at);
            }
            *peak_out = peak;
            return total;
        }
        if (n < MEMO_N && memo[n] != SENTINEL) {
            uint32_t total = steps + memo[n];
            for (int i = 0; i < pathlen; i++) {
                uint64_t v = path[i].n;
                if (v < MEMO_N) memo[v] = (uint16_t)(total - path[i].at);
            }
            *peak_out = peak;
            return total;
        }
        if (n < MEMO_N) {
            if (pathlen >= MAX_STEPS) { fprintf(stderr, "PATH OVERFLOW at n0=%llu\n", (unsigned long long)n0); exit(1); }
            path[pathlen].n = n;
            path[pathlen].at = steps;
            pathlen++;
        }
        if (n % 2 == 0) {
            n = n / 2;
        } else {
            if (n > (UINT64_MAX - 1) / 3) { fprintf(stderr, "OVERFLOW at n0=%llu\n", (unsigned long long)n0); exit(1); }
            n = 3 * n + 1;
        }
        steps++;
        if (n > peak) peak = n;
        if (steps > MAX_STEPS - 8) { fprintf(stderr, "NO CONVERGENCE (possible counterexample!) n0=%llu\n", (unsigned long long)n0); exit(2); }
    }
}

int main(int argc, char **argv) {
    uint64_t N = (argc > 1) ? strtoull(argv[1], NULL, 10) : 100000000ULL;
    const char *glide_csv = (argc > 2) ? argv[2] : "glide_records.csv";
    const char *peak_csv  = (argc > 3) ? argv[3] : "peak_records.csv";

    memo = malloc(MEMO_N * sizeof(uint16_t));
    if (!memo) { fprintf(stderr, "malloc failed\n"); return 1; }
    memset(memo, 0xFF, MEMO_N * sizeof(uint16_t));
    memo[1] = 0;

    FILE *fg = fopen(glide_csv, "w");
    FILE *fp = fopen(peak_csv, "w");
    fprintf(fg, "n,steps\n");
    fprintf(fp, "n,peak,peak_over_n\n");

    uint32_t max_steps = 0;
    uint64_t max_peak_ratio_n = 0;
    double max_peak_ratio = 0.0;
    uint64_t total_steps_sum = 0; /* for average glide length */
    uint64_t argmax_n = 0;
    uint64_t global_peak_value = 0;
    uint64_t global_peak_n = 0;

    for (uint64_t n = 1; n < N; n++) {
        uint64_t peak;
        uint32_t s = stopping_time(n, &peak);
        total_steps_sum += s;
        if (s > max_steps) {
            max_steps = s;
            argmax_n = n;
            fprintf(fg, "%llu,%u\n", (unsigned long long)n, s);
        }
        double ratio = (double)peak / (double)n;
        if (ratio > max_peak_ratio) {
            max_peak_ratio = ratio;
            max_peak_ratio_n = n;
            fprintf(fp, "%llu,%llu,%.6f\n", (unsigned long long)n, (unsigned long long)peak, ratio);
        }
        if (peak > global_peak_value) { global_peak_value = peak; global_peak_n = n; }
    }

    fclose(fg);
    fclose(fp);

    fprintf(stderr, "Verified Collatz conjecture (reaches 1) for all n in [1, %llu)\n", (unsigned long long)N);
    fprintf(stderr, "Max total stopping time: %u steps, achieved first at n=%llu\n", max_steps, (unsigned long long)argmax_n);
    fprintf(stderr, "Max peak/n ratio: %.4f at n=%llu\n", max_peak_ratio, (unsigned long long)max_peak_ratio_n);
    fprintf(stderr, "Global max trajectory value observed: %llu (at starting n=%llu)\n", (unsigned long long)global_peak_value, (unsigned long long)global_peak_n);
    fprintf(stderr, "Average total stopping time over [1,%llu): %.4f\n", (unsigned long long)N, (double)total_steps_sum / (double)(N - 1));

    free(memo);
    return 0;
}
