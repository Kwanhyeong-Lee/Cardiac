const fs = require('fs');
const d = require('docx');
const {Document,Packer,Paragraph,TextRun,HeadingLevel,Table,TableRow,TableCell,
       WidthType,ShadingType,AlignmentType,ImageRun,PageBreak} = d;

const BASE = "/sessions/vibrant-youthful-hopper/mnt/260421 (심장) - main/waveform_pinn";
const FIG  = `${BASE}/figures`;
const OUT  = `${BASE}/manuscripts/PaperA_reference_standard_floor.docx`;
const W = 9360;

const p = (t,o={}) => new Paragraph({
  spacing:{after:o.after??140, line:o.line??300},
  alignment:o.al, indent:o.indent,
  children:[new TextRun({text:t, bold:o.b, italics:o.i, size:o.size??22,
                         superScript:o.sup})]});
const rich = (runs,o={}) => new Paragraph({
  spacing:{after:o.after??140, line:o.line??300}, alignment:o.al,
  children:runs.map(r=> typeof r==="string"
    ? new TextRun({text:r,size:o.size??22})
    : new TextRun({text:r.t, bold:r.b, italics:r.i, size:o.size??22,
                   superScript:r.sup, subScript:r.sub}))});
const h1 = t => new Paragraph({text:t, heading:HeadingLevel.HEADING_1,
                               spacing:{before:340, after:160}});
const h2 = t => new Paragraph({text:t, heading:HeadingLevel.HEADING_2,
                               spacing:{before:260, after:130}});
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
      children:[new TextRun({text:String(t), bold, size:19})]})]}))});
  const out=[new Table({columnWidths:cw, width:{size:W,type:WidthType.DXA},
    rows:[mk(header,true,true), ...rows.map(r=>mk(r,false,false))]})];
  if(note) out.push(new Paragraph({spacing:{before:70,after:220},
    children:[new TextRun({text:note, size:18})]}));
  return out;
}

const kids = [];
kids.push(new Paragraph({alignment:AlignmentType.CENTER, spacing:{after:120},
  children:[new TextRun({text:"The reference standard sets the floor: the error a cardiac output model inherits from an uncalibrated pulse-contour device", bold:true, size:30})]}));
kids.push(p("Kwanhyeong Lee", {al:AlignmentType.CENTER, size:22, after:60}));
kids.push(p("Soonchunhyang University College of Medicine, Republic of Korea", {al:AlignmentType.CENTER, size:19, i:true, after:80}));
kids.push(p("Correspondence: alex026376@sch.ac.kr", {al:AlignmentType.CENTER, size:18, after:300}));

kids.push(h1("Abstract"));
kids.push(rich([
  {t:"Background. ",b:true},
  "Studies developing or validating cardiac output methods commonly use an uncalibrated pulse-contour monitor as the comparator, and interpret their agreement against the conventional 30% interchangeability threshold. If the comparator itself disagrees with an independent reference by more than that, the threshold cannot be reached by any method trained or evaluated against it."]));
kids.push(rich([
  {t:"Methods. ",b:true},
  "From VitalDB, an open surgical vital-signs database, we identified 24 patients carrying simultaneous uncalibrated pulse-contour (FloTrac-family) and continuous thermodilution pulmonary artery catheter cardiac output, together with a 500 Hz invasive arterial waveform. Agreement statistics were computed on patient medians with bias-corrected and accelerated bootstrap intervals. We then trained a neural network on the pulse-contour output of 866 further patients and measured its agreement with thermodilution, decomposing the total error into the inherited and model-specific components."]));
kids.push(rich([
  {t:"Results. ",b:true},
  "The device agreed with thermodilution with a percentage error of 40.1% (95% CI 32.5 to 50.4), r = 0.80 (0.55 to 0.94), bias −1.11 L/min and limits of agreement −3.93 to +1.71 L/min. The confidence interval excludes 30%. A model trained on the device reached a percentage error of 53.7% against thermodilution; because the two error sources are close to orthogonal, 53.7² = 40.1² + 35.7², leaving 35.7 percentage points attributable to imperfect imitation. Supplying the patient demographics that the device's own calibration uses reduced that component to 25.8 points and the total to 47.7%. Four-quadrant concordance of the device against thermodilution rose monotonically with the comparison interval, from 0.598 at 5 minutes to 0.744 at 30 minutes, and reached the conventional 92% threshold at no interval."]));
kids.push(rich([
  {t:"Conclusions. ",b:true},
  "An uncalibrated pulse-contour device imposes an error floor of approximately 40% on anything trained or validated against it, and continuous thermodilution cannot adjudicate trending below roughly 15 minutes. Studies using either as a comparator should report the comparator's own agreement in their cohort and interpret their results relative to that floor rather than to a fixed threshold."]));
kids.push(rich([{t:"Keywords. ",b:true},
  "cardiac output; pulse contour analysis; thermodilution; method comparison; Bland–Altman; VitalDB"], {after:280}));

kids.push(h1("Introduction"));
kids.push(p("Cardiac output can be estimated from the arterial pressure waveform without an indicator, and uncalibrated pulse-contour monitors are widely deployed for that purpose. Their convenience has made them the practical comparator for new methods: a study proposing a waveform-derived estimate will frequently validate it against a commercial pulse-contour monitor, because simultaneous thermodilution is invasive and rarely available."));
kids.push(p("The interpretive convention in this literature is the Critchley–Critchley percentage error, with 30% taken as the threshold below which two methods may be considered interchangeable. That threshold was derived on the assumption that the reference method carries an error of roughly 20%, so that a new method of comparable precision would yield a combined percentage error near 30%."));
kids.push(p("The assumption matters. If the comparator itself disagrees with an independent reference by substantially more than 20%, then a new method validated against that comparator inherits the disagreement, and the 30% target becomes unreachable irrespective of how well the new method performs. The magnitude of that inheritance is rarely quantified in the cohort at hand; it is more often assumed to be small, or cited from a meta-analytic range wide enough to accommodate any conclusion."));
kids.push(p("We set out to measure it directly in an open dataset, and to express it in a form a reader can apply to their own work. We report three things: the pulse-contour device's own agreement with continuous thermodilution, with a confidence interval; an arithmetic decomposition showing how much of a downstream model's error is inherited and how much is its own; and evidence, from the device's behaviour rather than from a model's, that continuous thermodilution cannot resolve short-interval trending."));

kids.push(h1("Methods"));
kids.push(h2("Data source and cohort"));
kids.push(p("VitalDB is an open, de-identified database of high-resolution intraoperative vital signs from Seoul National University Hospital, released under CC BY-NC-SA. We queried the public track index for cases carrying an invasive radial or femoral arterial pressure waveform (SNUADC/ART, 500 Hz) together with a device-reported cardiac output."));
kids.push(p("Three device families appear. EV1000 and Vigileo are uncalibrated pulse-contour monitors of the FloTrac family, which compute cardiac output from the arterial waveform itself; 924 cases carried one of these with a paired stroke volume. Vigilance is a continuous thermodilution pulmonary artery catheter, which measures flow by thermal indicator dilution and is therefore methodologically independent of the pressure waveform; 65 cases carried it. Twenty-four cases carried both, and these form the method-comparison cohort."));
kids.push(rich([{t:"All 24 paired cases, and all 33 cases carrying thermodilution without pulse contour, are liver transplant recipients. ",b:true},
  "This was not by design; it reflects which patients receive a pulmonary artery catheter at this institution. It is stated here because it bounds generalisation, and because it means that every figure reported for the model below was measured under a population shift relative to its training set."]));

kids.push(h2("Signal processing"));
kids.push(p("The arterial waveform was resampled to 100 Hz and restricted to physiologically plausible values (20–250 mmHg). Beats were detected by an upstroke threshold at the 90th percentile of the positive first difference with a 350 ms refractory period. Within each three-minute analysis window, beats were length-normalised and ensemble-averaged, and twenty-one shape descriptors were computed from the ensemble beat: systolic, diastolic, pulse and mean pressure; heart rate; the timing and pressure of the dicrotic notch, both absolute and as a fraction of the cycle; maximum and minimum dP/dt; systolic and diastolic areas and their ratio; form factor; upstroke time; beat length; and the skewness and kurtosis of the beat."));
kids.push(rich([
  "Device cardiac output was read over ",{t:"the same three-minute window",b:true},
  " as the waveform, not as a whole-case median. This matters: within-case cardiac output varies with a coefficient of variation of 13–19%, comparable to the between-patient spread, so pairing a whole-case summary with a single window is close to pairing each patient's waveform with a random draw from their own distribution. An earlier analysis that did so is retained in the reproducibility package as a documented negative example."]));
kids.push(p("Analysis windows were taken every five minutes, to a maximum of forty per case, giving 28,814 windows from 956 cases. All agreement statistics are computed on patient medians, so the reported n is the number of independent patients rather than the number of windows; computing them at window level would understate every confidence interval by approximately the square root of the number of windows per patient."));

kids.push(h2("Statistical analysis"));
kids.push(p("Agreement was quantified by Pearson correlation, Lin's concordance correlation coefficient, Bland–Altman bias and 95% limits of agreement, and the Critchley–Critchley percentage error, defined as twice the standard deviation of the differences divided by the mean of the two methods. Confidence intervals are bias-corrected and accelerated bootstrap intervals over 10,000 resamples."));
kids.push(p("Trending was assessed by four-quadrant concordance on consecutive within-patient changes, with a central exclusion zone of 15% of the reference mean, and by polar-plot angular agreement. The comparison interval was varied from 5 to 30 minutes. Bootstrap resampling for these statistics was clustered by patient."));
kids.push(p("The model referred to below is a feed-forward network trained on the pulse-contour cohort with a patient-disjoint split, using the waveform descriptors and, in one configuration, patient demographics. Its architecture is not the subject of this report and is described in full in the accompanying reproducibility package."));

kids.push(h1("Results"));
kids.push(h2("The device's own agreement with thermodilution"));
kids.push(rich([
  "Across the 24 paired patients the pulse-contour device agreed with continuous thermodilution with a percentage error of ",
  {t:"40.1% (95% CI 32.5 to 50.4)",b:true},
  ", Pearson r = 0.80 (0.55 to 0.94), concordance correlation 0.68, bias −1.11 L/min and limits of agreement from −3.93 to +1.71 L/min (Figure 1). The device read systematically lower than thermodilution, and the confidence interval on the percentage error excludes the conventional 30% interchangeability threshold."]));
kids.push(img("FigA1_device_benchmark.png", 560, 227));
kids.push(cap("Figure 1.| Pulse-contour cardiac output against continuous thermodilution in 24 liver transplant patients, one value per patient. (A) Method comparison against the line of identity. (B) Bland–Altman. The device that these studies commonly treat as a reference does not itself satisfy the criterion they apply to new methods."));

kids.push(h2("What a downstream model inherits"));
kids.push(rich([
  "A network trained on the device's output and evaluated against thermodilution reached a percentage error of 53.7%. Because the device's disagreement with thermodilution and the model's failure to reproduce the device are close to independent, the two combine in quadrature: 53.7",{t:"2",sup:true}," = 40.1",{t:"2",sup:true}," + 35.7",{t:"2",sup:true},
  ". Of the total, 40.1 percentage points are inherited and cannot be removed by any improvement to the model; 35.7 points are the model's own."]));
kids.push(rich([
  "FloTrac-family monitors compute cardiac output as the product of heart rate, the standard deviation of the arterial pressure, and a calibration factor derived from patient demographics. A model given only the waveform is therefore asked to reproduce a function of (waveform, demographics) from half its arguments. Supplying age, sex, height, weight, body mass index and body surface area — all present in VitalDB without missingness — raised the model's internal fidelity to the device from R",{t:"2",sup:true}," = 0.320 to 0.875 and reduced its own error component from 35.7 to 25.8 percentage points, bringing the total to 47.7% (Figure 2)."]));
kids.push(rich([
  "Demographics alone, with heart rate and mean pressure, reached R",{t:"2",sup:true}," = 0.658 — much of which is body size, since cardiac output scales with body surface area. That the two input sets together reach 0.875 while each alone reaches 0.320 and 0.658 indicates they carry complementary rather than redundant information."]));
kids.push(img("FigA2_error_decomposition.png", 600, 182));
kids.push(cap("Figure 2.| Error inherited from the reference and what demographics recover. (A) Total percentage error against thermodilution for four input configurations, with the device's own 40.1% marked; errors do not add linearly. (B) The model's own contribution, obtained in quadrature. (C) Internal fidelity to the device. Morphology and demographics are complementary."));
kids.push(...table([34,16,16,16,18],
  ["Model input","PE vs TD (%)","Own error (%)","Internal R²","Interpretation"],
  [["Waveform morphology","53.7","35.7","0.320","inherits floor, poor imitation"],
   ["Morphology + demographics","47.7","25.8","0.875","inherits floor, good imitation"],
   ["Demographics + HR/MAP","56.5","39.8","0.658","body size alone"],
   ["Linear model, both","49.2","28.5","0.521","network is not required for most of it"],
   ["Device itself","40.1","—","—","the floor"]],
  "Own error = √(PE² − 40.1²). Percentage error against continuous thermodilution, 33 patients for the model rows and 24 for the device row, patient medians."));

kids.push(h2("Trending resolution of the reference"));
kids.push(p("Absolute agreement and trending ability are distinct, and for hemodynamic monitoring trending is often the clinically decisive property. We therefore assessed four-quadrant concordance of the device against continuous thermodilution as a function of the interval between compared readings."));
kids.push(rich([
  "Concordance rose monotonically with interval: 0.598 at 5 minutes, 0.633 at 10, 0.733 at 15, 0.728 at 20 and 0.744 at 30 (Figure 3). ",
  {t:"The device is beat-responsive and is marketed specifically for trending",b:true},
  ", so a reference against which it registers near chance at five minutes is not resolving physiology at that timescale. Continuous thermodilution reports a trailing average over several minutes; consecutive short-interval readings are dominated by that averaging rather than by the patient. By 15 to 20 minutes real change begins to dominate and agreement improves."]));
kids.push(p("Neither the device nor a waveform-derived model reached the conventional 92% concordance threshold at any interval, and polar-plot radial limits of agreement were approximately ±200 degrees for both, indicating no agreement on the magnitude of changes. No trending claim is supportable from this data for either method."));
kids.push(img("FigA3_trending_resolution.png", 560, 227));
kids.push(cap("Figure 3.| Four-quadrant concordance of the pulse-contour device against continuous thermodilution as a function of the comparison interval, 15% exclusion zone, n above each point. The monotone rise is the signature of a reference whose own averaging window exceeds the interval being compared."));

kids.push(h2("A population where the model degrades, and what does not fix it"));
kids.push(rich([
  "Trained on general surgery and evaluated on liver transplant recipients, the model's patient-level R",{t:"2",sup:true}," fell from 0.81 to 0.50. The failure is not a calibration offset: the regression slope was 1.05 and the offset −0.32 L/min against a mean cardiac output of 5.7, while the residual standard deviation doubled from 0.66 to 1.39 L/min. An optimal affine recalibration — the best any correction factor can achieve — moved R",{t:"2",sup:true}," from 0.490 only to 0.519."]));
kids.push(rich([
  "What the model does carry is a usable signal about its own reliability. Mahalanobis distance from the training distribution correlated with absolute error (Spearman ρ = 0.298, p = 8×10",{t:"−124",sup:true},"). Abstaining on the most distant readings reduced the median error from 0.558 to 0.416 L/min and the 90th percentile from 1.98 to 1.30 L/min as coverage fell from 100% to 30%, while random abstention remained flat (Figure 4)."]));
kids.push(rich([
  {t:"The operating point is nonetheless poor. ",b:true},
  "Halving the tail error requires discarding 70% of readings; at a more plausible 30% abstention the 90th percentile falls only from 1.98 to 1.50 L/min and 23% of what remains is still wrong by more than 1 L/min. An ensemble of three initialisations performed no better than the input-distance score. Abstention is a working component, not a solution."]));
kids.push(img("FigA4_abstention.png", 560, 227));
kids.push(cap("Figure 4.| Selective prediction on transplant patients. (A) Median absolute error against coverage, with random abstention as control. (B) Ninetieth-percentile error and the share of retained readings still wrong by more than 1 L/min."));

kids.push(h1("Discussion"));
kids.push(p("Three findings bear directly on how method-comparison studies in this area should be read and written."));
kids.push(rich([
  {t:"First, the comparator is the floor. ",b:true},
  "An uncalibrated pulse-contour monitor disagreed with continuous thermodilution by 40.1%, with an interval excluding 30%. Any method trained or validated against such a device inherits that disagreement. A study reporting a percentage error of 45% against a pulse-contour comparator has not necessarily produced a worse method than one reporting 35% against thermodilution; the two numbers are not on the same scale. That the FloTrac family agrees imperfectly with thermodilution is established, but the consequence for downstream validation is not routinely drawn, and the inheritance is not usually quantified in the cohort at hand."]));
kids.push(rich([
  {t:"Second, the inheritance is arithmetic and can be applied by a reader. ",b:true},
  "Because the two error sources are close to orthogonal, a study can compute its own model-specific error as √(PE² − PE_device²) and report it alongside the total. This separates what the method contributes from what it inherited, and makes results obtained against different comparators comparable. In our case that separation was informative: it identified missing demographic inputs, which the device's calibration uses, as the cause of nearly a third of the model-specific error."]));
kids.push(rich([
  {t:"Third, a reference must be shown capable of resolving the quantity being claimed. ",b:true},
  "Continuous thermodilution cannot adjudicate trending below roughly 15 minutes, and the demonstration is not that our model failed against it but that a purpose-built beat-responsive monitor also did. A single-method study cannot make this argument; it requires a second method whose trending ability is not in question. Studies reporting trending should state the comparison interval and give evidence that their reference resolves it."]));
kids.push(p("A fourth observation is more specific. In the population where our model degraded, the degradation was in scatter rather than bias, and no correction factor could recover it — the ceiling on any affine recalibration was 0.03 of R². This distinction is worth making explicitly in clinical reports. A systematic bias is something a user can learn to allow for; irregular error is not, because nothing on the display indicates when a particular reading is wrong. Where a method degrades by scatter, the appropriate response is a reliability indicator rather than a correction, and the indicator's operating cost should be reported as a risk–coverage curve rather than as an accuracy figure at an unstated coverage."));

kids.push(h1("Limitations"));
kids.push(p("The method-comparison cohort comprises 24 patients from a single institution, all liver transplant recipients, and one pulse-contour device family. The confidence intervals are correspondingly wide, and at this sample size the percentage error cannot be distinguished from values between roughly 33% and 50%. The point estimate of the floor should be read as approximately 40% rather than as a precise figure."));
kids.push(p("Continuous thermodilution is itself an imperfect reference with a documented averaging lag, which is the subject of one of our findings rather than an assumption of the others; bolus thermodilution would provide a sharper comparator for trending but is not available in this dataset."));
kids.push(p("The abstention thresholds reported are descriptive. No threshold was pre-specified and none should be adopted from this analysis without a separate calibration set held out for that purpose."));

kids.push(h1("Data and code availability"));
kids.push(p("All data are from VitalDB (https://vitaldb.net), open access under CC BY-NC-SA. The extraction pipeline, agreement and trending statistics, abstention analysis, and the scripts that generate every figure in this report are released as a reproducibility package. Every number in the figures is read from saved result files rather than typed into the plotting code. The package includes the pre-specified analysis protocol with a dated deviation log, and the discarded first analysis retained as a documented negative example."));

kids.push(h1("References"));
const refs = [
 "Critchley LA, Critchley JA. A meta-analysis of studies using bias and precision statistics to compare cardiovascular measurements techniques. J Clin Monit Comput. 1999;15(2):85–91.",
 "Bland JM, Altman DG. Statistical methods for assessing agreement between two methods of clinical measurement. Lancet. 1986;327(8476):307–310.",
 "Lee HC, Park Y, Yoon SB, Yang SM, Park D, Jung CW. VitalDB, a high-fidelity multi-parameter vital signs database in surgical patients. Sci Data. 2022;9(1):279.",
 "Critchley LA, Lee A, Ho AM. A critical review of the ability of continuous cardiac output monitors to measure trends in cardiac output. Anesth Analg. 2010;111(5):1180–1192.",
 "Saugel B, Grothe O, Wagner JY. Tracking changes in cardiac output: statistical considerations on the 4-quadrant plot and the polar plot methodology. Anesth Analg. 2015;121(2):514–524.",
 "Lin LI. A concordance correlation coefficient to evaluate reproducibility. Biometrics. 1989;45(1):255–268.",
 "Efron B, Tibshirani RJ. An Introduction to the Bootstrap. Chapman & Hall; 1993.",
 "Montenij LJ, Buhre WF, Jansen JR, Kruitwagen CL, de Waal EE. Methodology of method comparison studies evaluating the validity of cardiac output monitors: a stepwise approach and checklist. Br J Anaesth. 2016;116(6):750–758.",
];
refs.forEach((r,i)=> kids.push(new Paragraph({
  spacing:{after:90, line:280}, indent:{left:340, hanging:340},
  children:[new TextRun({text:`${i+1}. ${r}`, size:20})]})));

const doc = new Document({sections:[{properties:{page:{
  size:{width:12240,height:15840},
  margin:{top:1440,right:1440,bottom:1440,left:1440}}}, children:kids}]});
fs.mkdirSync(`${BASE}/manuscripts`,{recursive:true});
Packer.toBuffer(doc).then(b=>{fs.writeFileSync(OUT,b);
  console.log("Paper A:", (b.length/1024).toFixed(0),"KB");});
