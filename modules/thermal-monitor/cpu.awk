# Cogan Thermal Monitor: CPU use since the previous sample.
# Files: <previous /proc/[pid]/stat lines> <current lines>; -v prev=<old /proc/stat cpu line> -v cur=<new one>.
# Prints "C <cpu%x10> <kernel%x10>" then "P <pct x10> <pid> <comm>" for the 5 busiest user processes.
function total(line,   a, n, i, t) { n = split(line, a, " "); t = 0; for (i = 2; i <= n; i++) t += a[i]; return t }
function idle(line,   a) { split(line, a, " "); return a[5] + a[6] }
function parse(line,   o, c, k, rest, f) {
    o = index(line, "("); c = 0
    while ((k = index(substr(line, c + 1), ")")) > 0) c += k      # the last ")" ends the name
    if (!o || c <= o) return 0
    PID = substr(line, 1, o - 2) + 0
    COMM = substr(line, o + 1, c - o - 1)
    rest = substr(line, c + 2)
    split(rest, f, " ")
    PPID = f[2] + 0; TICKS = f[12] + f[13]
    return 1
}
FILENAME == ARGV[1] { if (parse($0)) before[PID] = TICKS; next }
{
    if (!parse($0) || !(PID in before)) next
    d = TICKS - before[PID]
    if (d <= 0) next
    if (PID == 2 || PPID == 2) { kernel += d; next }            # kernel threads (children of kthreadd)
    gsub(/[^A-Za-z0-9_.+-]/, "_", COMM)
    for (i = 1; i <= 5; i++) if (!(i in top) || d > top[i]) {
        for (j = 5; j > i; j--) if ((j - 1) in top) { top[j] = top[j - 1]; tpid[j] = tpid[j - 1]; tcomm[j] = tcomm[j - 1] }
        top[i] = d; tpid[i] = PID; tcomm[i] = COMM; break
    }
}
END {
    dt = total(cur) - total(prev)
    if (prev == "" || dt <= 0) { print "C -1 -1"; exit }
    busy = dt - (idle(cur) - idle(prev))
    printf "C %d %d\n", int(busy * 1000 / dt + 0.5), int(kernel * 1000 / dt + 0.5)
    for (i = 1; i <= 5; i++) if (i in top) printf "P %d %d %s\n", int(top[i] * 1000 / dt + 0.5), tpid[i], tcomm[i]
}
