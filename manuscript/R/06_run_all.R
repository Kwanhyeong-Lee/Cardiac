# ============================================================
# 06_run_all.R  -- robust runner (resolves its own path)
# Run from anywhere:
#   Rscript ".../manuscript/R/06_run_all.R"
# - installs any missing packages
# - runs 01..05 with per-script OK/ERROR (never halts)
# - prints preview PNG mtimes so you can confirm all 5 refreshed
# ============================================================

# resolve this script's dir -> project root (works under Rscript)
args <- commandArgs(trailingOnly = FALSE)
this <- sub("^--file=", "", args[grep("^--file=", args)])
rdir <- if (length(this)) dirname(normalizePath(this)) else getwd()
root <- normalizePath(file.path(rdir, "../.."))
setwd(rdir)

# ensure required packages
need <- c("ggplot2", "patchwork", "jsonlite", "dplyr", "tidyr", "scales")
miss <- need[!vapply(need, requireNamespace, logical(1), quietly = TRUE)]
if (length(miss)) {
  cat("Installing missing packages:", paste(miss, collapse = ", "), "\n")
  install.packages(miss, repos = "https://cran.r-project.org")
}

scripts <- sort(list.files(rdir, pattern = "^0[1-5]_.*[.]R$"))
cat("\n=== Running", length(scripts), "figure scripts ===\n")
for (s in scripts) {
  cat("====", s, ": ")
  msg <- tryCatch({ source(s); "OK" },
                  error = function(e) paste("ERROR:", conditionMessage(e)))
  cat(msg, "\n")
}

figdir <- file.path(root, "manuscript", "figures")
cat("\n---- preview PNGs in", figdir, "----\n")
pv <- sort(list.files(figdir, pattern = "_preview[.]png$", full.names = TRUE))
if (!length(pv)) cat("(none found)\n")
for (f in pv) {
  fi <- file.info(f)
  cat(sprintf("%s  %7d B  %s\n",
              format(fi$mtime, "%m-%d %H:%M"), fi$size, basename(f)))
}
cat("\nDone. Expect 5 files dated today:",
    "Fig2_training, Fig3_anatomy, Fig4_validation, Fig5_pvloop, Fig6_cfd_pipeline\n")
