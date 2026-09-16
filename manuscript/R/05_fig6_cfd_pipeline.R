# ============================================================
# Fig 6. CFD Pipeline: Mesh Quality & Hemodynamic Setup
# Panels: (A) Mitral flow profile (E/A wave)  (B) Mesh cell distribution
#         (C) Simulation diagnostic summary
# Data:   cfd_simulation_analysis.json
# ============================================================
library(ggplot2)
library(jsonlite)
library(patchwork)
library(dplyr)

base_dir <- normalizePath(file.path(dirname(sys.frame(1)$ofile), "../.."), mustWork = FALSE)
if (!dir.exists(base_dir)) base_dir <- getwd()

cfd <- fromJSON(file.path(base_dir, "cfd_simulation_analysis.json"))

theme_pub <- theme_minimal(base_size = 11) +
  theme(
    panel.grid.minor = element_blank(),
    panel.border = element_rect(fill = NA, color = "grey40", linewidth = 0.5),
    plot.title = element_text(size = 12, face = "bold", hjust = 0),
    axis.title = element_text(size = 10),
    plot.margin = margin(5, 10, 5, 5)
  )

# --- Panel A: Mitral E/A wave inflow profile ---
# From 0/U boundary condition table (3 cardiac cycles, 0.8s each)
t_cycle <- c(0, 0.08, 0.12, 0.20, 0.28, 0.36, 0.44, 0.52, 0.60, 0.68, 0.80)
Q_m3s   <- c(0, 1.2e-4, 2.32e-4, 5e-5, 1e-5, 5e-5, 1.39e-4, 5e-5, 1e-5, 0, 0)
Q_mLs   <- Q_m3s * 1e6  # convert to mL/s

flow_df <- data.frame(t = t_cycle, Q = Q_mLs)

pA <- ggplot(flow_df, aes(t * 1000, Q)) +
  geom_area(fill = "#B2182B", alpha = 0.3) +
  geom_line(color = "#B2182B", linewidth = 1) +
  geom_point(color = "#B2182B", size = 2) +
  annotate("text", x = 120, y = 240, label = "E wave", size = 3.5, fontface = "bold") +
  annotate("text", x = 440, y = 150, label = "A wave", size = 3.5, fontface = "bold") +
  annotate("segment", x = 120, xend = 120, y = 0, yend = 232,
           linetype = "dotted", color = "grey50") +
  annotate("segment", x = 440, xend = 440, y = 0, yend = 139,
           linetype = "dotted", color = "grey50") +
  labs(x = "Time (ms)", y = "Flow Rate (mL/s)",
       title = "A  Mitral Inflow Profile") +
  theme_pub

# --- Panel B: Mesh composition ---
mesh_df <- data.frame(
  type = c("Hexahedra", "Polyhedra", "Prisms"),
  count = c(2660000, 119000, 12000),
  pct = c(95.3, 4.3, 0.4)
)
mesh_df$type <- factor(mesh_df$type, levels = mesh_df$type)

pB <- ggplot(mesh_df, aes(type, count / 1e6, fill = type)) +
  geom_col(alpha = 0.8, width = 0.6) +
  geom_text(aes(label = sprintf("%.1f%%", pct)), vjust = -0.5, size = 3.5) +
  scale_fill_manual(values = c("#2166AC", "#D6604D", "#4393C3"), guide = "none") +
  scale_y_continuous(labels = function(x) paste0(x, "M")) +
  labs(x = NULL, y = "Cell Count", title = "B  Mesh Composition (2.80M cells)") +
  theme_pub

# --- Panel C: v1 vs v2 config comparison ---
config_df <- data.frame(
  Parameter = c("deltaT", "maxCo", "ddtScheme", "divScheme",
                "minTetQuality", "nOuterCorr", "nLayers"),
  v1 = c("1e-5", "0.8", "backward", "linearUpwind",
         "-1e30\n(disabled)", "2", "3"),
  v2 = c("1e-6", "0.3", "Euler", "upwind",
         "1e-15\n(enabled)", "3", "2"),
  category = c("Stability", "Stability", "Accuracy", "Accuracy",
                "Mesh QC", "Convergence", "Mesh QC")
)

config_long <- config_df %>%
  tidyr::pivot_longer(cols = c(v1, v2), names_to = "version", values_to = "setting") %>%
  mutate(version = ifelse(version == "v1", "v1 (crashed)", "v2 (corrected)"))

cat_cols <- c("Stability" = "#D6604D", "Accuracy" = "#4393C3",
              "Mesh QC" = "#E66101", "Convergence" = "#1B7837")

pC <- ggplot(config_long, aes(version, Parameter, fill = category)) +
  geom_tile(alpha = 0.2, color = "grey70") +
  geom_text(aes(label = setting), size = 2.8) +
  scale_fill_manual(values = cat_cols, name = "Category") +
  labs(x = NULL, y = NULL,
       title = "C  Configuration: v1 (crashed) vs v2 (corrected)") +
  theme_pub +
  theme(legend.position = "bottom", legend.key.size = unit(0.4, "cm"),
        panel.grid = element_blank())

# --- Combine ---
fig6 <- (pA | pB) / pC + plot_layout(heights = c(1, 1.1)) +
  plot_annotation(
    title = "Figure 6. CFD Pipeline & Simulation Setup",
    subtitle = "pimpleFoam (OpenFOAM 2312), laminar flow, patient-specific LV geometry",
    theme = theme(
      plot.title = element_text(size = 13, face = "bold"),
      plot.subtitle = element_text(size = 9, color = "grey40")
    )
  )

ggsave(file.path(base_dir, "manuscript/figures/Fig6_cfd_pipeline.pdf"),
       fig6, width = 11, height = 8, device = cairo_pdf)
ggsave(file.path(base_dir, "manuscript/figures/Fig6_cfd_pipeline.png"),
       fig6, width = 11, height = 8, dpi = 300)

cat("Fig6 saved.\n")

# preview (embedded in the manuscript DOCX)
ggsave(file.path(base_dir, "manuscript/figures/Fig6_cfd_pipeline_preview.png"),
       fig6, width = 11, height = 8, dpi = 150)
