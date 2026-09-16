# ============================================================
# Fig 5. PV Loop & Port-Hamiltonian Energy Balance
# Panels: (A) PV loop  (B) Windkessel + dissipation parameters
#         (C) Port-Hamiltonian energy partition
#             (Stroke Work / Dissipation / Net SW / Potential Energy)
# Data:   windkessel_phpinn_results.json (v2, with r_diss), phpinn_v5_metrics.json
# ============================================================
library(ggplot2)
library(jsonlite)
library(patchwork)
library(dplyr)

# --- Paths (works under source(); falls back to CWD) ---
# --- robust paths (works under Rscript -e source; handles spaces/Korean in path) ---
root_of <- function() {
  for (cand in c("../..", "..", ".", getwd())) if (dir.exists(file.path(cand, "manuscript", "figures"))) return(normalizePath(cand))
  getwd()
}
base_dir <- root_of()
rj <- function(fname) jsonlite::fromJSON(paste(readLines(file.path(base_dir, fname), warn = FALSE), collapse = " "))

wk <- rj("windkessel_phpinn_results.json")
mt <- rj("phpinn_v5_metrics.json")

theme_pub <- theme_minimal(base_size = 11) +
  theme(
    panel.grid.minor = element_blank(),
    panel.border = element_rect(fill = NA, color = "grey40", linewidth = 0.5),
    plot.title = element_text(size = 12, face = "bold", hjust = 0),
    axis.title = element_text(size = 10),
    plot.margin = margin(5, 10, 5, 5)
  )

pv <- wk$pv_metrics
ph <- wk$phpinn

# port-Hamiltonian dissipation + dual efficiency (v2 JSON fields)
r_diss    <- pv$r_diss_mmHg_s_per_mL
E_diss    <- pv$E_dissipated_mmHg_mL
SW        <- pv$SW_mmHg_mL
SW_net    <- pv$SW_net_mmHg_mL
PE        <- pv$PE_mmHg_mL
PVA       <- pv$PVA_mmHg_mL
eff_gross <- pv$mechanical_efficiency_gross
eff_net   <- pv$mechanical_efficiency_net

# --- Panel A: PV Loop ---
Vd  <- ph$Vd
Emax <- ph$Emax
EDV <- pv$EDV_mL
ESV <- pv$ESV_mL
Pes <- pv$Pes_mmHg

v_esp <- seq(Vd, EDV + 20, length.out = 100)
p_esp <- Emax * (v_esp - Vd)
Eed <- 0.05
p_edp <- Eed * (v_esp - Vd)^1.5 / 50

theta <- seq(0, 2 * pi, length.out = 200)
cx <- (EDV + ESV) / 2
cy <- (pv$Pes_mmHg + 8) / 2
rx <- (EDV - ESV) / 2
ry <- (pv$Pes_mmHg - 8) / 2
loop_df <- data.frame(
  V = cx + rx * cos(theta) * (1 + 0.15 * sin(2 * theta)),
  P = cy + ry * sin(theta) * (1 + 0.1 * cos(theta))
)

pA <- ggplot() +
  geom_line(data = data.frame(V = v_esp, P = p_esp),
            aes(V, P), color = "#B2182B", linewidth = 0.6, linetype = "dashed") +
  geom_line(data = data.frame(V = v_esp, P = pmax(p_edp, 0)),
            aes(V, P), color = "#2166AC", linewidth = 0.6, linetype = "dashed") +
  geom_path(data = loop_df, aes(V, P), color = "#1B7837", linewidth = 1) +
  geom_point(data = data.frame(V = c(EDV, ESV), P = c(8, Pes)),
             aes(V, P), size = 3, color = c("#2166AC", "#B2182B")) +
  annotate("text", x = ESV - 3, y = Pes + 5, label = "ESP", size = 3, color = "#B2182B") +
  annotate("text", x = EDV + 3, y = 12, label = "EDP", size = 3, color = "#2166AC") +
  annotate("text", x = Vd + 5, y = max(p_esp) * 0.85,
           label = sprintf("ESPVR\nEmax = %.1f", Emax), size = 2.8, color = "#B2182B") +
  coord_cartesian(xlim = c(0, EDV + 30), ylim = c(-5, max(p_esp) * 0.5)) +
  labs(x = "LV Volume (mL)", y = "LV Pressure (mmHg)", title = "A  Pressure-Volume Loop") +
  theme_pub

# --- Panel B: Windkessel + dissipation parameters (5 facets; r_diss in red) ---
wk_params <- data.frame(
  param = c("R1 (Zc)", "R2 (Distal)", "C (Compl.)", "Ea/Emax", "r_diss"),
  value = c(wk$windkessel$R1, wk$windkessel$R2, wk$windkessel$C,
            pv$coupling_ratio_Ea_Emax, r_diss),
  ref_lo = c(0.03, 0.8, 1.0, 0.5, 0.010),
  ref_hi = c(0.10, 1.5, 2.5, 1.2, 0.050)
)
wk_params$param <- factor(wk_params$param, levels = wk_params$param)
bar_cols <- setNames(c("#2166AC", "#2166AC", "#2166AC", "#2166AC", "#B2182B"),
                     levels(wk_params$param))

pB <- ggplot(wk_params, aes(param, value, fill = param)) +
  geom_col(alpha = 0.75, width = 0.5) +
  geom_errorbar(aes(ymin = ref_lo, ymax = ref_hi), width = 0.3,
                color = "grey40", linetype = "dashed") +
  geom_text(aes(label = sprintf("%.3f", value)), vjust = -0.5, size = 2.7) +
  scale_fill_manual(values = bar_cols, guide = "none") +
  facet_wrap(~param, scales = "free", nrow = 1) +
  labs(x = NULL, y = "Value", title = "B  Windkessel + Dissipation Parameters") +
  theme_pub +
  theme(strip.text = element_text(size = 7), axis.text.x = element_blank())

# --- Panel C: Port-Hamiltonian energy partition (4 bars) ---
energy_df <- data.frame(
  component = c("Stroke Work\n(SW)", "Dissipation\n(E_diss)",
                "Net SW\n(SW - E_diss)", "Potential E\n(PE)"),
  value = c(SW, E_diss, SW_net, PE),
  pct   = c(SW / PVA * 100, E_diss / PVA * 100, SW_net / PVA * 100, PE / PVA * 100)
)
energy_df$component <- factor(energy_df$component, levels = energy_df$component)
en_cols <- c("#E66101", "#B2182B", "#1B7837", "#5E3C99")

pC <- ggplot(energy_df, aes(component, value, fill = component)) +
  geom_col(alpha = 0.85, width = 0.6) +
  geom_text(aes(label = sprintf("%.0f\n(%.1f%%)", value, pct)),
            vjust = -0.3, size = 2.7, lineheight = 0.9) +
  scale_fill_manual(values = en_cols, guide = "none") +
  coord_cartesian(ylim = c(0, max(energy_df$value) * 1.22)) +
  labs(x = NULL, y = "Energy (mmHg*mL)", title = "C  Energy Partition",
       subtitle = sprintf("Gross efficiency = %.1f%%   |   Net efficiency = %.1f%%",
                          eff_gross * 100, eff_net * 100)) +
  theme_pub +
  theme(plot.subtitle = element_text(size = 8, color = "grey30"))

# --- Combine ---
fig5 <- (pA | (pB / pC)) +
  plot_annotation(
    title = "Figure 5. PV Loop & Port-Hamiltonian Energy Balance",
    subtitle = sprintf("EF = %.1f%%, SV = %.0f mL, CO = %.2f L/min, Ea/Emax = %.2f, r_diss = %.4f",
                       pv$EF_pct, pv$SV_mL, wk$cfd_summary$CO_Lmin,
                       pv$coupling_ratio_Ea_Emax, r_diss),
    theme = theme(
      plot.title = element_text(size = 13, face = "bold"),
      plot.subtitle = element_text(size = 9, color = "grey40")
    )
  )

fig_dir <- file.path(base_dir, "manuscript/figures")
ggsave(file.path(fig_dir, "Fig5_pvloop.pdf"), fig5, width = 12, height = 7, device = cairo_pdf)
ggsave(file.path(fig_dir, "Fig5_pvloop.png"), fig5, width = 12, height = 7, dpi = 300)
# preview (embedded in the manuscript DOCX)
ggsave(file.path(fig_dir, "Fig5_pvloop_preview.png"), fig5, width = 12, height = 7, dpi = 150)

cat("Fig5 saved (Port-Hamiltonian energy balance).\n")
