# ============================================================
# Fig 6. Ablation study - physics constraints as inductive bias (ggplot)
# Panels: (A) R2 mean+/-SD across 4 models  (B) physical-validity violations
# Data:   ablation_summary.json  (3-seed random-split summary)
# ============================================================
library(ggplot2); library(jsonlite); library(patchwork); library(dplyr); library(tidyr)

# --- robust paths (works under Rscript -e source; handles spaces/Korean in path) ---
root_of <- function() {
  for (cand in c("../..", "..", ".", getwd())) if (dir.exists(file.path(cand, "manuscript", "figures"))) return(normalizePath(cand))
  getwd()
}
base_dir <- root_of()
rj <- function(fname) jsonlite::fromJSON(paste(readLines(file.path(base_dir, fname), warn = FALSE), collapse = " "))

d <- rj("ablation_summary.json")
r <- d$rows
N <- d$n_test
lab <- c(A = "A: pH-PINN\n(hard)", B = "B: Vanilla\nMLP",
         C = "C: No-structure\nPINN", D = "D: Soft-\nconstraint")
r$label <- factor(lab[r$letter], levels = lab)

theme_pub <- theme_minimal(base_size = 11) +
  theme(panel.grid.minor = element_blank(),
        panel.border = element_rect(fill = NA, color = "grey40", linewidth = 0.5),
        plot.title = element_text(size = 12, face = "bold", hjust = 0),
        axis.title = element_text(size = 10), plot.margin = margin(5, 10, 5, 5))

# Panel A: accuracy parity (mean +/- SD)
pA <- ggplot(r, aes(label, R2_mean)) +
  geom_col(fill = "#2166AC", width = 0.6, alpha = 0.9) +
  geom_errorbar(aes(ymin = R2_mean - R2_std, ymax = R2_mean + R2_std),
                width = 0.2, color = "grey20") +
  geom_text(aes(label = sprintf("%.3f", R2_mean)), vjust = -1.4, size = 3) +
  coord_cartesian(ylim = c(0.95, 0.982)) +
  labs(x = NULL, y = expression("Mean " * R^2 * " (13 targets)"),
       title = "A  Predictive accuracy (3 seeds, mean +/- SD)") +
  theme_pub

# Panel B: physical-validity violations
viol <- r %>%
  mutate(PSD = ifelse(R_PSD_viol < 0, 0, R_PSD_viol)) %>%
  select(label, Tneg = T_neg, Vneg = V_neg, PSD) %>%
  pivot_longer(-label, names_to = "type", values_to = "count") %>%
  mutate(type = recode(type, Tneg = "T < 0", Vneg = "V < 0", PSD = "R not PSD"))
viol$type <- factor(viol$type, levels = c("T < 0", "V < 0", "R not PSD"))

pB <- ggplot(viol, aes(label, count, fill = type)) +
  geom_col(position = position_dodge(0.72), width = 0.62) +
  scale_fill_manual(values = c("T < 0" = "#B2182B", "V < 0" = "#E66101", "R not PSD" = "#762A83")) +
  labs(x = NULL, y = sprintf("Violation count (of %d test cases)", N),
       title = "B  Physical-validity violations", fill = NULL) +
  theme_pub + theme(legend.position = "top")

fig6 <- pA | pB
fig6 <- fig6 + plot_annotation(
  title = "Figure 6. Ablation study - physics constraints as architectural inductive bias",
  subtitle = "Four matched-capacity models, 13 targets. Hard constraints (A) match accuracy while guaranteeing physical validity by construction.",
  theme = theme(plot.title = element_text(size = 13, face = "bold"),
                plot.subtitle = element_text(size = 9, color = "grey40")))

fd <- file.path(base_dir, "manuscript/figures")
ggsave(file.path(fd, "Fig6_ablation.pdf"), fig6, width = 11.5, height = 4.3, device = cairo_pdf)
ggsave(file.path(fd, "Fig6_ablation.png"), fig6, width = 11.5, height = 4.3, dpi = 300)
ggsave(file.path(fd, "Fig6_ablation_preview.png"), fig6, width = 11.5, height = 4.3, dpi = 150)
cat("Fig6 (ablation, ggplot) saved.\n")
