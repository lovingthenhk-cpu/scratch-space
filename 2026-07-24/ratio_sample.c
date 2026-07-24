/*
 * Empirical test of the standard Collatz "equilibrium heuristic":
 *
 *   Along a trajectory, an odd step  n -> 3n+1  multiplies by ~3,
 *   an even step  n -> n/2           divides by 2.
 *   For the trajectory to (on average) neither blow up nor collapse
 *   instantly, the standard heuristic argument says the number of
 *   even ("halving") steps e and odd ("3n+1") steps o occurring along
 *   a long trajectory should satisfy   2^e ~= 3^o,   i.e.
 *       e/o -> log2(3) = 1.5849625...
 *       o/(o+e) -> 1/(1+log2(3)) = 0.3868528...   (odd-step fraction)
 *       e/(o+e) -> log2(3)/(1+log2(3)) = 0.6131472...  (even-step fraction)
 *
 * This program samples many random starting values n at different
 * orders of magnitude, walks the *actual* trajectory (no memo -- we
 * want the real odd/even counts, not a shortcut), and records:
 *     n, total_steps, odd_steps, even_steps, odd_fraction, peak, peak/n
 *
 * so we can check, empirically, whether longer trajectories really do
 * converge toward the predicted odd_fraction ~= 0.386853.
 */
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <math.h>
#include <time.h>

#define MAX_STEPS 2000000

/* returns 1 on success, 0 on overflow-abort (trajectory grew too large to
 * represent safely in uint64, or exceeded MAX_STEPS without reaching 1) */
static int walk(uint64_t n0, uint64_t *out_steps, uint64_t *out_odd, uint64_t *out_even, uint64_t *out_peak) {
    uint64_t n = n0;
    uint64_t odd = 0, even = 0;
    uint64_t peak = n0;
    uint64_t steps = 0;
    while (n != 1) {
        if (n % 2 == 0) {
            n = n / 2;
            even++;
        } else {
            if (n > (UINT64_MAX - 1) / 3) return 0; /* would overflow */
            n = 3 * n + 1;
            odd++;
        }
        steps++;
        if (n > peak) peak = n;
        if (steps > MAX_STEPS) return 0;
    }
    *out_steps = steps; *out_odd = odd; *out_even = even; *out_peak = peak;
    return 1;
}

int main(int argc, char **argv) {
    const char *outcsv = (argc > 1) ? argv[1] : "ratio_samples.csv";
    unsigned int seed = (argc > 2) ? (unsigned int)strtoul(argv[2], NULL, 10) : 12345u;
    srand(seed);

    FILE *f = fopen(outcsv, "w");
    fprintf(f, "n,steps,odd_steps,even_steps,odd_fraction,peak,peak_over_n\n");

    /* Sample many random n at each of several orders of magnitude,
     * from 10^3 up to 10^13 (kept well below uint64 overflow territory
     * even accounting for large peak/n excursions seen in the n<1e9 scan). */
    int samples_per_decade = 5000;
    for (int decade = 3; decade <= 18; decade++) {
        uint64_t lo = 1;
        for (int i = 0; i < decade; i++) lo *= 10;
        uint64_t hi = lo * 10;
        for (int s = 0; s < samples_per_decade; s++) {
            /* random n uniformly in [lo, hi) using 63-bit combination of rand() calls */
            uint64_t span = hi - lo;
            uint64_t r = ((uint64_t)rand() << 32) ^ ((uint64_t)rand() << 16) ^ (uint64_t)rand();
            uint64_t n0 = lo + (r % span);
            if (n0 % 2 == 0) n0 += 1; /* prefer odd starts; doesn't matter much but avoids trivial short evens-only prefix */

            uint64_t steps, odd, even, peak;
            if (!walk(n0, &steps, &odd, &even, &peak)) continue; /* skip overflow/non-converging (unexpected) */
            double odd_frac = (double)odd / (double)(odd + even);
            fprintf(f, "%llu,%llu,%llu,%llu,%.6f,%llu,%.6f\n",
                    (unsigned long long)n0, (unsigned long long)steps,
                    (unsigned long long)odd, (unsigned long long)even,
                    odd_frac, (unsigned long long)peak, (double)peak / (double)n0);
        }
    }
    /* Phase 2: "long-trajectory hunt". Typical random n has a glide length
     * close to the population mean (~7*ln n), so the buckets above run out
     * of long trajectories fast. To get more samples with large step
     * counts (needed to see the heuristic converge further), we do a
     * best-effort random search across a wide magnitude range and keep
     * only the samples that beat a minimum step threshold. This is not
     * exhaustive (no claim of finding *the* record) -- just a way to
     * surface more long-trajectory data points cheaply. */
    int hunt_samples = 400000;
    int kept = 0;
    for (int i = 0; i < hunt_samples; i++) {
        int decade = 9 + (rand() % 9); /* log-uniform-ish over 10^9 .. 10^17 */
        uint64_t lo = 1;
        for (int j = 0; j < decade; j++) lo *= 10;
        uint64_t hi = lo * 10;
        uint64_t span = hi - lo;
        uint64_t r = ((uint64_t)rand() << 32) ^ ((uint64_t)rand() << 16) ^ (uint64_t)rand();
        uint64_t n0 = lo + (r % span);
        if (n0 % 2 == 0) n0 += 1;

        uint64_t steps, odd, even, peak;
        if (!walk(n0, &steps, &odd, &even, &peak)) continue;
        if (steps < 700) continue; /* only keep the long-trajectory outliers */
        double odd_frac = (double)odd / (double)(odd + even);
        fprintf(f, "%llu,%llu,%llu,%llu,%.6f,%llu,%.6f\n",
                (unsigned long long)n0, (unsigned long long)steps,
                (unsigned long long)odd, (unsigned long long)even,
                odd_frac, (unsigned long long)peak, (double)peak / (double)n0);
        kept++;
    }
    fprintf(stderr, "long-trajectory hunt: kept %d/%d samples with steps>=700\n", kept, hunt_samples);

    fclose(f);
    fprintf(stderr, "done, wrote samples to %s\n", outcsv);
    return 0;
}
