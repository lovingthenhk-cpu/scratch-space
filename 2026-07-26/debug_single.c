#include <stdio.h>
#include <stdint.h>

#define DIVERGE_THRESHOLD ((uint64_t)1e17)
#define DIVERGE_MIN_STEPS 30

int main(int argc, char **argv) {
    uint64_t n = strtoull(argv[1], NULL, 10);
    uint64_t q = strtoull(argv[2], NULL, 10);
    int max_steps = argc > 3 ? atoi(argv[3]) : 100;
    printf("step 0: n=%llu\n", (unsigned long long)n);
    for (int step = 0; step < max_steps; step++) {
        if (n == 1) { printf("REACHED_ONE at step %d\n", step); return 0; }
        if (n % 2 == 0) { n = n/2; }
        else {
            if (n > (UINT64_MAX - 1)/q) { printf("OVERFLOW GUARD at step %d, n=%llu\n", step, (unsigned long long)n); return 0; }
            n = q*n + 1;
        }
        printf("step %d: n=%llu%s\n", step+1, (unsigned long long)n, (n > DIVERGE_THRESHOLD && step > DIVERGE_MIN_STEPS) ? "  <-- OVER THRESHOLD" : "");
        if (n > DIVERGE_THRESHOLD && step > DIVERGE_MIN_STEPS) { printf("DIVERGED at step %d\n", step+1); return 0; }
    }
    printf("did not resolve in %d steps, n=%llu\n", max_steps, (unsigned long long)n);
    return 0;
}
