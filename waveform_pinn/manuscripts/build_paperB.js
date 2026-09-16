const fs = require('fs');
const d = require('docx');
const {Document,Packer,Paragraph,TextRun,HeadingLevel,Table,TableRow,TableCell,
       WidthType,ShadingType,AlignmentType,ImageRun} = d;

const BASE = "/sessions/vibrant-youthful-hopper/mnt/260421 (심장) - main/waveform_pinn";
const FIG  = `${BASE}/figures`;
const OUT  = `${BASE}/manuscripts/PaperB_constraint_scope.docx`;
const W = 9360;

const p = (t,o={}) => new Paragraph({
  spacing:{after:o.after??140, line:o.line??300}, alignment:o.al,
  children:[new TextRun({text:t, bold:o.b, italics:o.i, size:o.size??22})]});
const rich = (runs,o={}) => new Paragraph({
  spacing:{after:o.after??140, line:o.line??300}, alignment:o.al,
  children:runs.map(r=> typeof r==="string"
    ? new TextRun({text:r,size:o.size??22})
    : new TextRun({text:r.t, bold:r.b, italics:r.i, size:o.size??22,
                   superScript:r.sup, subScript:r.sub, font:r.mono?"Consolas":undefined}))});
const h1 = t => new Paragraph({text:t, heading:HeadingLevel.HEADING_1,
                               spacing:{before:340, after:160}});
const h2 = t => new Paragraph({text:t, heading:HeadingLevel.HEADING_2,
                               spacing:{before:260, after:130}});
const eq = t => new Paragraph({alignment:AlignmentType.CENTER,
  spacing:{before:120, after:150},
  children:[new TextRun({text:t, size:22, font:"Cambria Math", italics:true})]});
const img = (f,w,hh) => new Paragraph({alignment:AlignmentType.CENTER,
  spacing:{before:180, after:90},
  children:[new ImageRun({type:"png", data:fs.readFileSync(`${FIG}/${f}`),
                          transformation:{width:w, height:hh}})]});
const cap = t => new Paragraph({spacing:{after:260},
  children:[new TextRun({text:t.split("|")[0], bold:true, size:19}),
            new TextRun({text:t.split("|")[1], size:19})]});

function table(cols, header, rows, note){
  const tot = cols.reduce((a,b)=>a+b,0), s = W/tot;
  const cw = cols.map(c=>Math.round(c*s));
  const mk = (arr,bold,shade)=> new TableRow({children: arr.map((t,i)=> new TableCell({
    width:{size:cw[i],type:WidthType.DXA},
    shading: shade?{type:ShadingType.CLEAR, fill:"EFEFEF"}:undefined,
    children:[new Paragraph({spacing:{before:50,after:50},
      children:[new TextRun({text:String(t), bold, size:18})]})]}))});
  const out=[new Table({columnWidths:cw, width:{size:W,type:WidthType.DXA},
    rows:[mk(header,true,true), ...rows.map(r=>mk(r,false,false))]})];
  if(note) out.push(new Paragraph({spacing:{before:70,after:220},
    children:[new TextRun({text:note, size:18})]}));
  return out;
}

const kids = [];
kids.push(new Paragraph({alignment:AlignmentType.CENTER, spacing:{after:120},
  children:[new TextRun({text:"Architectural energy constraints in physiological neural networks: what they guarantee, what they do not, and what that costs", bold:true, size:30})]}));
kids.push(p("Kwanhyeong Lee", {al:AlignmentType.CENTER, size:22, after:60}));
kids.push(p("Soonchunhyang University College of Medicine, Republic of Korea", {al:AlignmentType.CENTER, size:19, i:true, after:80}));
kids.push(p("Correspondence: alex026376@sch.ac.kr", {al:AlignmentType.CENTER, size:18, after:300}));

kids.push(h1("Abstract"));
kids.push(rich([
  "Physics-informed neural networks for physiology commonly impose conservation or passivity through penalty terms, which shape the loss surface without removing inadmissible states from the model's range. We compare imposing port-Hamiltonian energy structure ",
  {t:"architecturally",i:true}," — non-negative kinetic and potential energy through softplus outputs, the Hamiltonian formed as their sum rather than predicted, and a Cholesky-parameterised dissipation matrix — against the same constraints applied as a penalty and against no constraint at all. Four capacity-matched architectures were evaluated on three datasets spanning two input modalities and an order of magnitude in difficulty (R",{t:"2",sup:true},
  " from 0.25 to 0.97), and on two surgical populations never seen during training."]));
kids.push(rich([
  "Predictive accuracy was indistinguishable across architectures on every dataset. Physical validity was not: the architecturally constrained model produced zero violations in 16,619 held-out windows, an identical-capacity unconstrained model produced a non-positive-semidefinite dissipation matrix in ",
  {t:"every",i:true}," window, and a tuned penalty produced exactly one violation in 16,619. The separation held on both unseen populations. We further show that the guarantee extends to exactly the quantities it constrains and no further: the model's reported output is unconstrained and can be driven negative under synthetic displacement, a construction that propagates the guarantee to the output closes this at no accuracy cost, and even so it guarantees positivity rather than plausibility. Under a real clinical distribution shift the output failure does not occur for any architecture, so the propagated guarantee is mathematically real and its practical benefit undemonstrated. We report a diagnostic error found in the process: counting positive-semidefiniteness violations with a fixed absolute tolerance manufactures violations of a property that cannot be violated when eigenvalues span orders of magnitude."]));
kids.push(rich([{t:"Index terms. ",b:true},
  "physics-informed neural networks, port-Hamiltonian systems, hard constraints, distribution shift, cardiovascular modelling"], {after:280}));

kids.push(h1("I. Introduction"));
kids.push(p("A physiological state estimator can attain high predictive accuracy while internally representing quantities that cannot exist: negative kinetic energy, a dissipation operator with a negative eigenvalue, a Hamiltonian that does not equal the sum of its parts. Whether this matters depends on what the state is for. If only the reported scalar is consumed, an inadmissible internal state is a curiosity. If the state is passed to a simulator, a controller, or a counterfactual query, it is a defect."));
kids.push(p("The standard remedy is a penalty: add the violated inequality to the loss and weight it. This is effective where the training data constrain the network and offers nothing where they do not, which is precisely the regime a digital twin is built to explore. The alternative is to construct the model so that the violating region is not in its range — softplus for a non-negative quantity, Cholesky factorisation for a positive-semidefinite matrix, algebraic composition instead of separate prediction."));
kids.push(p("The alternative is not new. What is not established is whether it costs anything, whether the difference from a penalty is real or merely nominal, and — the question we found most consequential — what exactly the guarantee covers. Papers reporting hard constraints frequently do not distinguish the constrained quantities from the reported ones, and in-distribution the distinction is invisible."));
kids.push(p("This paper answers those three questions on a cardiovascular state estimator, with three contributions and one correction."));
kids.push(rich(["1) The constraint is free. Four capacity-matched architectures are indistinguishable in accuracy across three datasets and two unseen surgical populations."], {after:60}));
kids.push(rich(["2) The constraint is real, and a penalty is not equivalent to it. Zero violations by construction against one in 16,619 for a tuned penalty and a failure in every window without constraints."], {after:60}));
kids.push(rich(["3) The guarantee is scoped. It covers the constrained quantities; the reported output is not among them; propagating the construction closes the gap at no cost; and even propagated it delivers the predicate encoded and nothing adjacent."], {after:60}));
kids.push(rich(["4) A diagnostic correction: a fixed absolute tolerance on eigenvalues spanning several orders of magnitude reports violations of a property that holds as a matter of algebra."], {after:200}));

kids.push(h1("II. Methods"));
kids.push(h2("A. Model family"));
kids.push(rich([
  "The state is x = (q, p) ∈ ℝ",{t:"5",sup:true},
  " with q the volumes of the left ventricle, left atrium and arterial compartment, and p the mitral and aortic pressures. The network emits the state, the kinetic and potential energies T and V, the Hamiltonian H, a dissipation matrix R, and the clinical target. Inference is per-window and steady-state; time is not an input and no trajectory is integrated."]));
kids.push(p("Five variants differ only in how the energy structure is imposed."));
kids.push(...table([12,88],
  ["Model","Construction"],
  [["A","Hard architectural constraints. T = softplus(·) ≥ 0 and V = softplus(·) ≥ 0; H = T + V by composition, never predicted separately; R = LLᵀ with a softplus diagonal, so R ⪰ 0 as a matter of algebra."],
   ["B","Vanilla multilayer perceptron. T, V and H are free outputs with no relation to one another; no dissipation matrix."],
   ["C","No-structure. Encoder and decoder topology identical to A, but T, V and H are predicted independently and R is symmetrised without factorisation, so it may have negative eigenvalues."],
   ["D","Soft constraints. Architecture as C; the same three conditions are added to the loss as penalties with unit weight."],
   ["E","Output-constrained. Architecture as A, with the reported output formed as CO = SV / T_period from strictly positive components rather than decoded freely."]],
  "Parameter counts on the 27-input dataset: A 56,983, B 56,644, C 58,402, D 58,402, E 39,720. Models A through D are matched to within 3%; E is smaller, which is a limitation of its comparison and is stated as such."));
kids.push(rich([
  "Because A emits R ⪰ 0 for every input, the passivity inequality dH/dt ≤ y",{t:"⊤",sup:true},"u implied by the port-Hamiltonian form holds pointwise without a penalty term and without reliance on the training distribution."]));

kids.push(h2("B. Datasets"));
kids.push(p("Three datasets were used, chosen to span input modality and difficulty rather than to be comparable to one another."));
kids.push(...table([26,20,18,36],
  ["Dataset","Input","Approx. R²","Notes"],
  [["1. Clinical features","11 echocardiographic and hemodynamic variables","0.97","4,241 subjects, patient-level split. Targets are closed-form functions of the inputs, so the accuracy is near-saturated by construction."],
   ["2. Waveform morphology","21 shape descriptors of the ensemble arterial beat","0.25","866 patients, 22,400 windows. Near the floor of what is learnable from these inputs alone."],
   ["3. Waveform + demographics","the above plus age, sex, height, weight, BMI, BSA","0.88","956 patients, 28,814 windows. The principal dataset for this report."]],
  "Splits are by patient throughout, with an explicit disjointness assertion. Three random seeds per configuration."));

kids.push(h2("C. Distribution shift"));
kids.push(p("For the shift experiments, models were trained on general surgery only (389 patients) and evaluated on thoracic surgery (226) and liver transplantation (175), neither seen in training. One-lung ventilation and the anhepatic phase produce hemodynamics absent from the training population, and neither can be dismissed as an artefact of the probe."));
kids.push(rich([
  "A synthetic probe was also run, displacing held-out inputs by 0, 6 and 24 training standard deviations per feature. ",
  {t:"We report it as a stress test whose premise is inputs that cannot occur",b:true},
  ": at 24 standard deviations the displacement produces systolic pressures below diastolic and negative areas. It is included because the two probes disagree, and that disagreement is one of the paper's results."]));

kids.push(h2("D. Violation diagnostics"));
kids.push(rich([
  "Violations are counted as the number of held-out windows with T < 0, with V < 0, and with a non-positive-semidefinite R. For the last, ",
  {t:"a relative tolerance is required",b:true},
  ". R = LLᵀ is positive semidefinite as a matter of algebra, but its eigenvalues span 10",{t:"3",sup:true},"–10",{t:"4",sup:true},
  " at extreme inputs, and a float32 eigendecomposition then returns minima near −10",{t:"−4",sup:true},
  " — a relative magnitude of 9.2×10",{t:"−8",sup:true},", which is float32 epsilon. Judged against a fixed −10",{t:"−6",sup:true},
  " these register as breaches of a property that cannot be breached."]));
kids.push(rich([
  "Our first implementation used the absolute threshold and reported model E violating R ⪰ 0 in 14, 42, 77 and 106 windows as displacement increased. Recomputing in float64 against λ",{t:"min",sub:true}," < −10",{t:"−6",sup:true}," λ",{t:"max",sub:true},
  " removes every one of these, including four and seven previously attributed to model A. Counts for model C are unaffected: its R is symmetrised but not factorised, and its violations are real. Any study counting positive-semidefiniteness breaches with a fixed tolerance on a quantity of varying scale is exposed to the same artefact."]));

kids.push(h1("III. Results"));
kids.push(h2("A. Accuracy is not the discriminating axis"));
kids.push(rich([
  "On dataset 3, the four capacity-matched architectures reached mean R",{t:"2",sup:true},
  " of 0.875 ± 0.023 (A), 0.878 ± 0.024 (B), 0.872 ± 0.018 (C) and 0.872 ± 0.018 (D) over three seeds. The largest gap, 0.006, is smaller than every model's seed-to-seed standard deviation. Percentage error against an independent thermodilution reference was likewise indistinguishable, from 47.7% to 48.4%. The same ordering — that is, no ordering — was obtained on datasets 1 and 2 (Figure 1A)."]));
kids.push(rich([
  "We emphasise that near-saturated accuracy on dataset 1 reflects the closed-form construction of its targets, and near-floor accuracy on dataset 2 reflects a genuinely hard problem. That the constraint is free at ",
  {t:"both",i:true}," extremes is a stronger statement than that it is free at either."]));

kids.push(h2("B. Physical validity is"));
kids.push(rich([
  "Over 16,619 held-out windows (three seeds × 5,540), model A produced ",
  {t:"zero",b:true},
  " violations of any kind. Model C produced a non-positive-semidefinite dissipation matrix in 16,619 windows — every one — together with 7,763 negative kinetic and 6,027 negative potential energies. Model B, which has no dissipation matrix, produced 11,452 and 8,708. Model D, with a tuned penalty, produced exactly ",
  {t:"one",b:true}," negative potential energy and nothing else (Figure 1B, 1C)."]));
kids.push(...table([16,18,16,16,16,18],
  ["Model","R² (3 seeds)","PE vs TD (%)","T < 0","V < 0","R ⋡ 0"],
  [["A: hard","0.875 ± 0.023","47.93 ± 0.42","0","0","0"],
   ["B: vanilla MLP","0.878 ± 0.024","47.74 ± 0.24","11,452","8,708","n/a"],
   ["C: no structure","0.872 ± 0.018","48.03 ± 0.21","7,763","6,027","16,619"],
   ["D: soft (penalty)","0.872 ± 0.018","48.43 ± 0.70","0","1","0"]],
  "Dataset 3, totals over three seeds and 16,619 held-out windows. Percentage error is against continuous thermodilution on 33 patients, patient medians."));
kids.push(rich([
  "That single violation is the result, not a rounding artefact. A rate of 6×10",{t:"−5",sup:true},
  " is invisible in any ordinary evaluation and still means the failure mode is reachable; the penalty has made it improbable where the data constrain the network, and has said nothing about anywhere else. Model A cannot reach it at any rate, on any input, because the softplus and the Cholesky factorisation remove it from the model's range. The distinction is between rare and impossible."]));
kids.push(rich([
  "On dataset 2 model D reached zero violations. We report this rather than omit it: on a smaller and lower-dimensional problem the penalty was sufficient, and the separation between penalty and architecture is a function of problem scale as well as of principle."]));
kids.push(img("FigB1_ablation.png", 620, 188));
kids.push(cap("Figure 1.| Ablation over four capacity-matched architectures. (A) Mean R² on three datasets spanning two input modalities and an order of magnitude in difficulty; the architectures are indistinguishable on all three. (B) Physical-validity violations on dataset 3, seed means. (C) Models A and D at scale."));

kids.push(h2("C. The separation holds under real clinical shift"));
kids.push(rich([
  "Trained on general surgery and evaluated on thoracic surgery and liver transplantation, accuracy remained indistinguishable across architectures (thoracic R",{t:"2",sup:true},
  " 0.84, 0.84 and 0.80 for A, C and E). Models A and E produced zero violations on every set and every seed; model C produced a non-positive-semidefinite dissipation matrix in all 6,202 thoracic and all 6,007 transplant windows, on patients it had never seen (Figure 3)."]));
kids.push(rich([
  "Accuracy itself degraded sharply on transplantation — R",{t:"2",sup:true},
  " from 0.81 to 0.50 — and did so ",{t:"identically for every architecture",b:true},
  ". The constraints govern admissibility, not accuracy, and this is what that looks like when stated plainly rather than implied."]));

kids.push(h2("D. Where the guarantee stops"));
kids.push(rich([
  "Under synthetic displacement, model A's internal state remained admissible at every level while its reported cardiac output reached −29.6 L/min in 94 of 400 windows at 24 standard deviations — no better than the entirely unconstrained model C, at 104. The softplus and the Cholesky factorisation constrain the internal energy objects; the decoder producing the output is an ordinary linear map with nothing attached to it."]));
kids.push(rich([
  "Model E forms the output as CO = SV / T",{t:"period",sub:true},
  " from strictly positive components, so positivity holds for the same reason T ≥ 0 holds. It produced zero negative outputs at every displacement tested, at R",{t:"2",sup:true},
  " 0.869 against A's 0.875 and percentage error 46.7% against 47.7%, with 39,720 parameters against 56,983 (Figure 2A)."]));
kids.push(rich([
  {t:"Under real clinical shift, none of this occurs. ",b:true},
  "No model produced a single negative output on thoracic or transplant patients — not A, not E, and not the unconstrained C. Output ranges stayed between roughly 1.8 and 12 L/min in every group (Figure 2B). The objection that a model fed physiologically impossible inputs may return impossible outputs without that implying anything about deployment is correct, and two surgical specialities with genuinely different hemodynamics do not come close to provoking the failure."]));
kids.push(rich([
  {t:"We therefore report model E's contribution as a construction with a proof rather than as a fix for an observed problem. ",b:true},
  "It guarantees CO > 0 by construction; nothing in this data shows a case where that guarantee is what prevented a bad output."]));
kids.push(rich([
  "Nor does it guarantee more than it encodes. At 24 standard deviations model E's maximum output reached 386 L/min — positive throughout, and roughly seventy times a physiological value. The bulk behaved (median 3.4 L/min, 11 of 400 above 25), but no upper bound exists because none was constructed."]));
kids.push(img("FigB2_scope.png", 580, 216));
kids.push(cap("Figure 2.| The guarantee covers the constrained quantities and stops there. (A) Synthetic displacement: A's internal state stays admissible while its output does not; E is at zero throughout. (B) Real clinical shift: no model produces a negative output, including the unconstrained C."));
kids.push(img("FigB3_distribution_shift.png", 580, 216));
kids.push(cap("Figure 3.| Trained on 389 general-surgery patients, evaluated on 226 thoracic and 175 transplant patients never seen. (A) Accuracy degrades by 0.34 identically for every architecture. (B) Non-positive-semidefinite dissipation matrices: A and E at zero on every set, C failing in every window."));

kids.push(h2("E. Accuracy under shift requires a separate mechanism"));
kids.push(rich([
  "The transplant degradation is scatter, not bias: regression slope 1.05, offset −0.32 L/min, but residual standard deviation doubled from 0.66 to 1.39. An optimal affine recalibration moved R",{t:"2",sup:true},
  " from 0.490 only to 0.519, the ceiling being r",{t:"2",sup:true},". No correction factor addresses a failure of this shape."]));
kids.push(rich([
  "Distance from the training distribution does predict the model's own error (Spearman ρ = 0.298, p = 8×10",{t:"−124",sup:true},
  "). Abstaining on the most distant windows reduced the median absolute error from 0.558 to 0.416 L/min and the 90th percentile from 1.98 to 1.30 as coverage fell to 30%, against a flat random-abstention control. The operating point is poor — 23% of retained readings at 70% coverage are still wrong by more than 1 L/min — and an ensemble of three initialisations was no better than the input-distance score."]));
kids.push(rich([
  "Three properties, three mechanisms, none substituting for another: the energy constraints deliver admissibility, they say nothing about accuracy, and accuracy under shift needs a reliability mechanism that is itself insufficient here. This is the same lesson as §III-D, arriving from the other direction."]));

kids.push(h1("IV. Discussion"));
kids.push(rich([
  "The claim this work supports is narrower than the one it would be convenient to make. Architectural energy constraints are free and they work; a penalty is not equivalent to them; and both statements now hold across three datasets and two unseen clinical populations. What the work does ",
  {t:"not",i:true}," support is that a model with an admissible internal state is thereby more trustworthy. Under the only realistic distribution shift we could construct, the unconstrained model's outputs were as well behaved as the constrained model's."]));
kids.push(rich([
  {t:"The benefit is conditional and the condition is stated. ",b:true},
  "An admissible internal state is worth having if the state is consumed — a forward rollout, a model-predictive controller, a simulator taking the estimate as an initial condition. Each of these can be broken by a negative energy or an energy-generating dissipation operator in a way that a reported scalar cannot. We built no such consumer, and so we claim a capability at known cost rather than a demonstrated benefit."]));
kids.push(rich([
  "The scoping result generalises beyond this application. A constraint guarantees exactly the predicate it is built from and nothing adjacent to it: softplus on T and V guarantees non-negative energy, not a sensible output; SV / T",{t:"period",sub:true},
  " guarantees positive cardiac output, not a bounded one. A paper claiming a physically constrained model owes the reader the list of predicates it actually enforces, and the distinction is invisible in-distribution — all architectures look identical at zero displacement."]));
kids.push(p("Finally, the diagnostic error is worth reporting rather than silently fixing. A fixed absolute tolerance applied to a quantity whose scale varies by four orders of magnitude will manufacture violations, and we manufactured 239 of them before noticing that they were violations of something algebraically impossible. The correction is a relative tolerance computed in double precision."));

kids.push(h1("V. Limitations"));
kids.push(p("Model E is not capacity-matched to model A, so its comparison confounds the output construction with a smaller decoder; the matched variant is outstanding."));
kids.push(rich([
  "The cohort carrying the independent thermodilution reference consists entirely of liver transplant recipients. ",
  {t:"This was not appreciated when the cohorts were defined",b:true},
  ", and it means every accuracy figure reported against that reference was measured under a population shift relative to the training set. The transplant R",{t:"2",sup:true},
  " of 0.50 is therefore the relevant generalisation figure rather than the 0.88 obtained in-distribution."]));
kids.push(p("The abstention thresholds are descriptive; none was pre-specified and none should be adopted without a separate calibration set. The synthetic probe uses one noise realisation per displacement level. Dataset 1 results are carried over from prior work on the same architecture."));

kids.push(h1("VI. Reproducibility"));
kids.push(p("The analysis protocol was fixed before the results existed and includes a power analysis, four pre-specified negative controls — label permutation, feature ablation, a linear baseline, and random abstention — and a dated deviation log recording every design change with its reason. Five apparent findings were overturned during the study by controls that had been put in place before the corresponding result was computed: a data-alignment defect that would have produced a false negative; a power trap that would have made the primary endpoint uninterpretable; the diagnostic artefact described in §II-D; the non-replication of the synthetic probe reported in §III-D; and a volumetric result that appeared at one seed and vanished across three. Each is documented, and the discarded analyses are retained in the package rather than deleted."));
kids.push(p("All data are from VitalDB, open access under CC BY-NC-SA. Code, derived tables, the protocol with its deviation log, and the scripts generating every figure are released together. Figure values are read from saved result files rather than typed into the plotting code."));

kids.push(h1("References"));
const refs = [
 "van der Schaft A, Jeltsema D. Port-Hamiltonian systems theory: an introductory overview. Found Trends Syst Control. 2014;1(2-3):173–378.",
 "Raissi M, Perdikaris P, Karniadakis GE. Physics-informed neural networks: a deep learning framework for solving forward and inverse problems involving nonlinear partial differential equations. J Comput Phys. 2019;378:686–707.",
 "Greydanus S, Dzamba M, Yosinski J. Hamiltonian neural networks. Adv Neural Inf Process Syst. 2019;32.",
 "Cranmer M, Greydanus S, Hoyer S, Battaglia P, Spergel D, Ho S. Lagrangian neural networks. ICLR Deep Differential Equations Workshop. 2020.",
 "Donti PL, Rolnick D, Kolter JZ. DC3: a learning method for optimization with hard constraints. Int Conf Learn Represent. 2021.",
 "Suga H, Sagawa K. Instantaneous pressure-volume relationships and their ratio in the excised, supported canine left ventricle. Circ Res. 1974;35(1):117–126.",
 "Westerhof N, Lankhaar JW, Westerhof BE. The arterial Windkessel. Med Biol Eng Comput. 2009;47(2):131–141.",
 "Lee HC, Park Y, Yoon SB, Yang SM, Park D, Jung CW. VitalDB, a high-fidelity multi-parameter vital signs database in surgical patients. Sci Data. 2022;9(1):279.",
 "Critchley LA, Critchley JA. A meta-analysis of studies using bias and precision statistics to compare cardiovascular measurements techniques. J Clin Monit Comput. 1999;15(2):85–91.",
 "El-Yaniv R, Wiener Y. On the foundations of noise-free selective classification. J Mach Learn Res. 2010;11:1605–1641.",
 "Lakshminarayanan B, Pritzel A, Blundell C. Simple and scalable predictive uncertainty estimation using deep ensembles. Adv Neural Inf Process Syst. 2017;30.",
 "Loshchilov I, Hutter F. Decoupled weight decay regularization. Int Conf Learn Represent. 2019.",
];
refs.forEach((r,i)=> kids.push(new Paragraph({
  spacing:{after:90, line:280}, indent:{left:340, hanging:340},
  children:[new TextRun({text:`[${i+1}] ${r}`, size:20})]})));

const doc = new Document({sections:[{properties:{page:{
  size:{width:12240,height:15840},
  margin:{top:1440,right:1440,bottom:1440,left:1440}}}, children:kids}]});
fs.mkdirSync(`${BASE}/manuscripts`,{recursive:true});
Packer.toBuffer(doc).then(b=>{fs.writeFileSync(OUT,b);
  console.log("Paper B:", (b.length/1024).toFixed(0),"KB");});
