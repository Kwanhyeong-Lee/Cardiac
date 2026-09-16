# ============================================================
# 00_install_packages.R
# pH-PINN Cardiac Digital Twin Manuscript - R package install
# Usage: Rscript 00_install_packages.R
# ============================================================

pkgs <- c(
  "ggplot2", "patchwork", "jsonlite", "dplyr", "tidyr",
  "scales", "ggrepel", "RColorBrewer", "cowplot", "Cairo"
)

for (p in pkgs) {
  if (!requireNamespace(p, quietly = TRUE)) {
    install.packages(p, repos = "https://cran.r-project.org")
  }
}
cat("All packages installed. Run: Rscript 01_fig2_training.R\n")
