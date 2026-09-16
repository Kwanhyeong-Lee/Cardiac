# ============================================================
# Fig 3. Cardiac Anatomy: Multi-Structure Assembly & 20-Case Analysis
# Panels: (A) 20-case chamber volumes  (B) Wall thickness  (C) Assembly inventory
# Data:   all_20cases_cardiac_analysis.json, wall_thickness_analysis.json,
#         cardiac_assembly_summary.json
# ============================================================
library(ggplot2)
library(jsonlite)
library(patchwork)
library(dplyr)
library(tidyr)

# --- robust paths (works under Rscript -e source; handles spaces/Korean in path) ---
root_of <- function() {
  for (cand in c("../..", "..", ".", getwd())) if (dir.exists(file.path(cand, "manuscript", "figures"))) return(normalizePath(cand))
  getwd()
}
base_dir <- root_of()
rj <- function(fname) jsonlite::fromJSON(paste(readLines(file.path(base_dir, fname), warn = FALSE), collapse = " "))

cases  <- rj("all_20cases_cardiac_analysis.json")
wt     <- rj("wall_thickness_analysis.json")
asm    <- rj("cardiac_assembly_summary.json")

theme_pub <- theme_minimal(base_size = 11) +
  theme(
    panel.grid.minor = element_blank(),
    panel.border = element_rect(fill = NA, color = "grey40", linewidth = 0.5),
    plot.title = element_text(size = 12, face = "bold", hjust = 0),
    axis.title = element_text(size = 10),
    plot.margin = margin(5, 10, 5, 5)
  )

# --- Panel A: Chamber volumes across 20 cases ---
vol_df <- do.call(rbind, lapply(seq_len(nrow(cases)), function(i) {
  row <- cases[i, ]
  vols <- row$vols
  data.frame(
    case = as.character(row$case),
    LV = vols$LV, RV = vols$RV, LA = vols$LA,
    RA = vols$RA, Myo = vols$Myo, Aorta = vols$Aorta
  )
}))

vol_long <- vol_df %>%
  pivot_longer(-case, names_to = "Chamber", values_to = "Volume_mL") %>%
  mutate(Chamber = factor(Chamber, levels = c("LV", "RV", "LA", "RA", "Myo", "Aorta")))

chamber_cols <- c(
  LV = "#E41A1C", RV = "#377EB8", LA = "#4DAF4A",
  RA = "#984EA3", Myo = "#FF7F00", Aorta = "#A65628"
)

pA <- ggplot(vol_long, aes(Chamber, Volume_mL, fill = Chamber)) +
  geom_boxplot(alpha = 0.7, outlier.size = 1, width = 0.6) +
  geom_jitter(width = 0.15, size = 0.8, alpha = 0.5) +
  scale_fill_manual(values = chamber_cols) +
  labs(x = NULL, y = "Volume (mL)", title = "A") +
  theme_pub + theme(legend.position = "none")

# --- Panel B: Wall thickness distribution ---
edges <- wt$hist_edges
counts <- wt$histogram
mids <- (edges[-length(edges)] + edges[-1]) / 2
wt_df <- data.frame(thickness = mids, count = counts)

pB <- ggplot(wt_df, aes(thickness, count)) +
  geom_col(fill = "#E66101", alpha = 0.8, width = diff(edges)[1] * 0.9) +
  geom_vline(xintercept = wt$mean, linetype = "dashed", color = "black", linewidth = 0.5) +
  annotate("text", x = wt$mean + 0.5, y = max(counts) * 0.9,
           label = sprintf("Mean = %.1f mm\nSD = %.1f mm", wt$mean, wt$std),
           size = 3, hjust = 0) +
  labs(x = "Wall Thickness (mm)", y = "Count", title = "B") +
  theme_pub

# --- Panel C: Assembly inventory (13 structures) ---
meshes_df <- data.frame(
  structure = sapply(asm$meshes, function(m) m$name),
  triangles = sapply(asm$meshes, function(m) m$triangles) / 1000,
  source_type = sapply(asm$meshes, function(m) {
    s <- m$source
    if (grepl("MM-WHS", s)) "CT segmentation"
    else if (grepl("STACOM", s)) "STACOM atlas"
    else if (grepl("Parametric", s)) "Parametric"
    else if (grepl("K-means", s)) "K-means split"
    else "Other"
  })
)
meshes_df$structure <- factor(meshes_df$structure,
                               levels = rev(meshes_df$structure))

src_cols <- c("CT segmentation" = "#2166AC", "STACOM atlas" = "#B2182B",
              "Parametric" = "#1B7837", "K-means split" = "#762A83")

pC <- ggplot(meshes_df, aes(triangles, structure, fill = source_type)) +
  geom_col(alpha = 0.85, width = 0.7) +
  scale_fill_manual(values = src_cols, name = "Source") +
  labs(x = "Triangles (×10³)", y = NULL, title = "C") +
  theme_pub +
  theme(legend.position = "bottom", legend.key.size = unit(0.4, "cm"),
        axis.text.y = element_text(size = 8))

# --- Combine ---
fig3 <- (pA | pB) / pC + plot_layout(heights = c(1, 1.2)) +
  plot_annotation(
    title = "Figure 3. Multi-Structure Cardiac Anatomy",
    subtitle = sprintf("13 structures, %s triangles total, %d MM-WHS cases analyzed",
                       format(asm$total_triangles, big.mark = ","), nrow(cases)),
    theme = theme(
      plot.title = element_text(size = 13, face = "bold"),
      plot.subtitle = element_text(size = 9, color = "grey40")
    )
  )

ggsave(file.path(base_dir, "manuscript/figures/Fig3_anatomy.pdf"),
       fig3, width = 10, height = 8, device = cairo_pdf)
ggsave(file.path(base_dir, "manuscript/figures/Fig3_anatomy.png"),
       fig3, width = 10, height = 8, dpi = 300)

cat("Fig3 saved.\n")

# preview (embedded in the manuscript DOCX)
ggsave(file.path(base_dir, "manuscript/figures/Fig3_anatomy_preview.png"),
       fig3, width = 10, height = 8, dpi = 150)
