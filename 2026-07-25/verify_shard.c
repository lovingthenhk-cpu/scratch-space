/*
 * Collatz (3x+1) conjecture: bulk verification + record tracking, SHARDED.
 *
 * This is a generalization of 2026-07-24/verify.c to support splitting the
 * range [1, N) into independent contiguous shards [N_start, N_end) that can
 * be run as separate OS processes (e.g. on different cores), while still
 * producing a globally-correct "record" stream (glide records = new maximum
 * total-stopping-time so far; peak records = new maximum peak/n ratio so far).
 *
 * Key idea: since n increases monotonically across the whole scan and we
 * process shards in increasing order of n, the running maximum at the start
 * of shard k+1 is exactly the final running maximum of shard k. So we accept
 * "init_max_steps" / "init_max_peak_ratio" as command-line thresholds: a
 * value in this shard is only emitted as a record if it strictly exceeds the
 * threshold carried in from all earlier shards. Each shard also has its own
 * independent memoization table (recomputed per shard; MEMO_N controls its
 * size/cost) since the memo is just a speed optimization and does not affect
 * correctness of the shard's own step counts.
 *
 * Each shard writes a small "handoff" text file with the final running
 * max_steps / max_peak_ratio / global_peak_value / count / sum_steps so the
 * next shard (or a merge script) can pick up where this one left off.
 *
 * Usage:
 *   verify_shard N_start N_end glide_csv peak_csv handoff_out \
 *                [init_max_steps] [init_max_peak_ratio] [memo_n]
 */
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <math.h>

static uint64_t MEMO_N = 20000000ULL;
static uint16_t *memo;
#define SENTINEL 0xFFFFu
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
    if (argc < 6) {
        fprintf(stderr, "usage: %s N_start N_end glide_csv peak_csv handoff_out [init_max_steps] [init_max_peak_ratio] [memo_n]\n", argv[0]);
        return 1;
    }
    uint64_t N_start = strtoull(argv[1], NULL, 10);
    uint64_t N_end   = strtoull(argv[2], NULL, 10);
    const char *glide_csv = argv[3];
    const char *peak_csv  = argv[4];
    const char *handoff_out = argv[5];
    uint32_t max_steps = (argc > 6) ? (uint32_t)strtoul(argv[6], NULL, 10) : 0;
    double max_peak_ratio = (argc > 7) ? strtod(argv[7], NULL) : 0.0;
    if (argc > 8) MEMO_N = strtoull(argv[8], NULL, 10);

    memo = malloc(MEMO_N * sizeof(uint16_t));
    if (!memo) { fprintf(stderr, "malloc failed\n"); return 1; }
    memset(memo, 0xFF, MEMO_N * sizeof(uint16_t));
    if (MEMO_N > 1) memo[1] = 0;

    FILE *fg = fopen(glide_csv, "w");
    FILE *fp = fopen(peak_csv, "w");
    fprintf(fg, "n,steps\n");
    fprintf(fp, "n,peak,peak_over_n\n");

    uint64_t argmax_n = 0;
    uint64_t max_peak_ratio_n = 0;
    uint64_t total_steps_sum = 0;
    uint64_t global_peak_value = 0;
    uint64_t global_peak_n = 0;
    uint64_t count = 0;

    uint64_t start = (N_start < 1) ? 1 : N_start;
    for (uint64_t n = start; n < N_end; n++) {
        uint64_t peak;
        uint32_t s = stopping_time(n, &peak);
        total_steps_sum += s;
        count++;
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

    FILE *fh = fopen(handoff_out, "w");
    fprintf(fh, "n_start=%llu\n", (unsigned long long)N_start);
    fprintf(fh, "n_end=%llu\n", (unsigned long long)N_end);
    fprintf(fh, "max_steps=%u\n", max_steps);
    fprintf(fh, "max_steps_n=%llu\n", (unsigned long long)argmax_n);
    fprintf(fh, "max_peak_ratio=%.6f\n", max_peak_ratio);
    fprintf(fh, "max_peak_ratio_n=%llu\n", (unsigned long long)max_peak_ratio_n);
    fprintf(fh, "global_peak_value=%llu\n", (unsigned long long)global_peak_value);
    fprintf(fh, "global_peak_n=%llu\n", (unsigned long long)global_peak_n);
    fprintf(fh, "count=%llu\n", (unsigned long long)count);
    fprintf(fh, "sum_steps=%llu\n", (unsigned long long)total_steps_sum);
    fclose(fh);

    fprintf(stderr, "Shard [%llu, %llu): verified, no counterexample.\n", (unsigned long long)N_start, (unsigned long long)N_end);
    fprintf(stderr, "  max_steps=%u (n=%llu), max_peak_ratio=%.4f (n=%llu)\n",
            max_steps, (unsigned long long)argmax_n, max_peak_ratio, (unsigned long long)max_peak_ratio_n);
    fprintf(stderr, "  mean steps this shard: %.4f, count=%llu\n",
            (double)total_steps_sum / (double)count, (unsigned long long)count);

    free(memo);
    return 0;
}
