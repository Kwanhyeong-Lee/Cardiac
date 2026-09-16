# ============================================================
# Fig 2. Port-Hamiltonian PINN Training Convergence
# Panels: (A) Loss curves  (B) R2 convergence
#         (C) Hamiltonian structure consistency |H-(T+V)| under
#             scalar dissipation R(x) = r_diss * I  (PSD-constrained)
# Data:   phpinn_v5_history.json, phpinn_v5_metrics.json,
#         windkessel_phpinn_results.json
# ============================================================
library(ggplot2)
library(jsonlite)
library(patchwork)
library(dplyr)
library(scales)

# --- Paths (works under source(); falls back to CWD) ---
# --- robust paths (works under Rscript -e source; handles spaces/Korean in path) ---
root_of <- function() {
  for (cand in c("../..", "..", ".", getwd())) if (dir.exists(file.path(cand, "manuscript", "figures"))) return(normalizePath(cand))
  getwd()
}
base_dir <- root_of()
rj <- function(fname) jsonlite::fromJSON(paste(readLines(file.path(base_dir, fname), warn = FALSE), collapse = " "))

hist_data <- rj("phpinn_v5_history.json")
metrics   <- rj("phpinn_v5_metrics.json")
wk        <- rj("windkessel_phpinn_results.json")
r_diss    <- wk$phpinn$r_diss
psd_viol  <- metrics$R_PSD_viol

n_epochs <- length(hist_data$tl)
df <- data.frame(
  epoch      = 1:n_epochs,
  train_loss = hist_data$tl,
  val_loss   = hist_data$vl,
  r2_cardiac = hist_data$r2c,
  r2_ees     = hist_data$r2e,
  h_error    = hist_data$he
)

# --- Theme ---
theme_pub <- theme_minimal(base_size = 11) +
  theme(
    text = element_text(family = "sans"),
    panel.grid.minor = element_blank(),
    panel.border = element_rect(fill = NA, color = "grey40", linewidth = 0.5),
    plot.title = element_text(size = 12, face = "bold", hjust = 0),
    axis.title = element_text(size = 10),
    legend.position = "top",
    legend.title = element_blank(),
    plot.margin = margin(5, 10, 5, 5)
  )

cols <- c("Train" = "#2166AC", "Validation" = "#B2182B")

# --- Panel A: Loss ---
df_loss <- df %>%
  tidyr::pivot_longer(cols = c(train_loss, val_loss),
                      names_to = "set", values_to = "loss") %>%
  mutate(set = ifelse(set == "train_loss", "Train", "Validation"))

pA <- ggplot(df_loss, aes(epoch, loss, color = set)) +
  geom_line(linewidth = 0.7) +
  scale_color_manual(values = cols) +
  scale_y_log10(labels = label_number(accuracy = 0.01)) +
  labs(x = "Epoch", y = "Loss (log scale)", title = "A  Training & Validation Loss") +
  annotate("text", x = n_epochs * 0.68, y = min(df$val_loss) * 1.4,
           label = sprintf("Final val: %.3f", tail(df$val_loss, 1)),
           size = 3, color = "grey30") +
  theme_pub

# --- Panel B: R2 (final values shown in legend) ---
lab_card <- sprintf("Cardiac output (R2 = %.3f)", tail(df$r2_cardiac, 1))
lab_ees  <- sprintf("Ees elastance (R2 = %.3f)", tail(df$r2_ees, 1))
df_r2 <- df %>%
  tidyr::pivot_longer(cols = c(r2_cardiac, r2_ees),
                      names_to = "target", values_to = "r2") %>%
  mutate(target = ifelse(target == "r2_cardiac", lab_card, lab_ees))
df_r2$target <- factor(df_r2$target, levels = c(lab_card, lab_ees))

r2_cols <- setNames(c("#1B7837", "#762A83"), c(lab_card, lab_ees))

pB <- ggplot(df_r2, aes(epoch, r2, color = target)) +
  geom_line(linewidth = 0.7) +
  scale_color_manual(values = r2_cols) +
  coord_cartesian(ylim = c(0.3, 1.0)) +
  geom_hline(yintercept = 0.95, linetype = "dashed", color = "grey50", linewidth = 0.3) +
  annotate("text", x = 5, y = 0.965, label = "R2 = 0.95", size = 2.5,
           color = "grey50", hjust = 0) +
  labs(x = "Epoch", y = expression(R^2), title = "B  R-squared Convergence") +
  guides(color = guide_legend(nrow = 2)) +
  theme_pub +
  theme(legend.text = element_text(size = 7.5))

# --- Panel C: Hamiltonian structure consistency under R(x) = r_diss * I ---
h_final <- tail(df$h_error, 1)
pC <- ggplot(df, aes(epoch, h_error)) +
  geom_line(color = "#D95F02", linewidth = 0.7) +
  scale_y_continuous(labels = label_scientific()) +
  labs(x = "Epoch",
       y = expression("|H - (T + V)|"~(J)),
       title = "C  Hamiltonian Consistency") +
  annotate("label", x = 1, y = max(df$h_error),
           label = sprintf("R(x) = r_diss*I  (R >= 0, PSD)\nPSD violations: %d\nr_diss = %.3f",
                           psd_viol, r_diss),
           size = 2.5, hjust = 0, vjust = 1, color = "grey20",
           fill = "grey95", label.size = 0.25, lineheight = 0.95) +
  annotate("text", x = n_epochs * 0.60, y = max(df$h_error) * 0.90,
           label = sprintf("Final: %.1e J", h_final),
           size = 3, color = "#D95F02") +
  theme_pub +
  theme(legend.position = "none")

# --- Combine ---
fig2 <- pA + pB + pC + plot_layout(ncol = 3, widths = c(1, 1, 1)) +
  plot_annotation(
    title = "Figure 2. Port-Hamiltonian PINN Training Convergence",
    subtitle = sprintf(
      "150 epochs | %s parameters | best epoch %d | port-Hamiltonian dynamics with scalar dissipation R(x) = r_diss*I",
      format(metrics$n_params, big.mark = ","), metrics$best_ep),
    theme = theme(
      plot.title = element_text(size = 13, face = "bold"),
      plot.subtitle = element_text(size = 9, color = "grey40")
    )
  )

fig_dir <- file.path(base_dir, "manuscript/figures")
ggsave(file.path(fig_dir, "Fig2_training.pdf"), fig2, width = 12, height = 4, device = cairo_pdf)
ggsave(file.path(fig_dir, "Fig2_training.png"), fig2, width = 12, height = 4, dpi = 300)
# preview (embedded in the manuscript DOCX)
ggsave(file.path(fig_dir, "Fig2_training_preview.png"), fig2, width = 12, height = 4, dpi = 150)

cat("Fig2 saved (Port-Hamiltonian).\n")
