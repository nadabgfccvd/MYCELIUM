CC ?= gcc
SRC = vec.c bench.c
VARIANTS = O2 O3 O3native O2unroll

FLAGS_O2 = -O2
FLAGS_O3 = -O3
FLAGS_O3native = -O3 -march=native
FLAGS_O2unroll = -O2 -funroll-loops

all: $(VARIANTS:%=bench_%)

bench_%: $(SRC) vec.h
	$(CC) $(FLAGS_$*) -o $@ $(SRC)

check: all
	@for v in $(VARIANTS); do ./bench_$$v | sed "s/^/$$v: /"; done
	@test $$(for v in $(VARIANTS); do ./bench_$$v | grep -o "checksum=[^ ]*"; done | sort -u | wc -l) -eq 1 && echo CHECKSUMS_AGREE

clean:
	rm -f bench_O2 bench_O3 bench_O3native bench_O2unroll

.PHONY: all check clean
