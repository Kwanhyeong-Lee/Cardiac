%% =========================================================================
%  AI 기반 심근독성(Cardiotoxicity) 정량 평가 파이프라인 - MATLAB 버전
%  PV 루프 & Frank-Starling 모델 기반
%
%  순천향대학교 의과대학 | 심장 및 순환생리 실습
%  2026년 4월
%  =========================================================================
%  Required Toolbox: Statistics and Machine Learning Toolbox
%  =========================================================================
close all; clear; clc;

%% =====================================================================
%  STEP 1: 생리학 모델 정의 (Physiological Model)
%  - Time-Varying Elastance (Suga & Sagawa, 1974)
%  =====================================================================
fprintf('=' .* ones(1,70)); fprintf('\n');
fprintf('  STEP 1: 생리학 모델 정의 (Physiological Model)\n');
fprintf('=' .* ones(1,70)); fprintf('\n');

% Guyton Ch.9 + Burkhoff 2005 기반 파라미터
V0    = 10.0;     % Dead volume (mL)
A_EDP = 0.337;    % EDPVR scaling constant (mmHg)

% 함수 정의 (아래 로컬 함수 섹션 참조)
% edpvr(v, bedp), espvr(v, ees), calc_hemodynamics(edv, aop, ees, hr, bedp)

% 정상값 검증
normal = calc_hemodynamics(120, 100, 2.5, 72, 0.028, V0, A_EDP);
fprintf('\n[검증] 정상값:\n');
fprintf('  EDV=%.0fmL, ESV=%.0fmL, SV=%.0fmL, EF=%.1f%%, CO=%.1fL/min, EDP=%.1fmmHg\n', ...
    normal.EDV, normal.ESV, normal.SV, normal.EF, normal.CO, normal.EDP);
fprintf('  → Guyton Ch.9 정상범위와 일치\n\n');

%% =====================================================================
%  STEP 2: 합성 환자 데이터 생성 (Synthetic Patient Cohort)
%  =====================================================================
fprintf('=' .* ones(1,70)); fprintf('\n');
fprintf('  STEP 2: 합성 환자 데이터 생성\n');
fprintf('=' .* ones(1,70)); fprintf('\n');

rng(42);  % 재현성
N = 1000;

% 등급별 비율: Normal 35%, Mild 30%, Moderate 20%, Severe 15%
grade_dist = [0.35, 0.30, 0.20, 0.15];
grade_names = {'Normal', 'Mild', 'Moderate', 'Severe'};

% DOX 용량 범위 (mg/m²)
dox_ranges = [0 100; 100 300; 300 450; 450 600];
% Ees 범위 (mmHg/mL)
ees_ranges = [2.0 3.0; 1.5 2.0; 1.0 1.5; 0.5 1.0];

% 등급 배정
grades = randsample(0:3, N, true, grade_dist)';

% 사전 할당
data = struct();
patient_id   = (1:N)';
age          = zeros(N,1);
sex          = zeros(N,1);
bsa          = zeros(N,1);
dox_dose     = zeros(N,1);
ees_arr      = zeros(N,1);
edv_arr      = zeros(N,1);
aop_arr      = zeros(N,1);
hr_arr       = zeros(N,1);
bedp_arr     = zeros(N,1);
troponin     = zeros(N,1);
bnp_arr      = zeros(N,1);
gls_arr      = zeros(N,1);

% 혈역학 결과
EDV_out = zeros(N,1); ESV_out = zeros(N,1); SV_out = zeros(N,1);
EF_out = zeros(N,1);  CO_out = zeros(N,1);  EDP_out = zeros(N,1);
ESP_out = zeros(N,1);  Peak_LVP_out = zeros(N,1); SW_out = zeros(N,1);
Ees_out = zeros(N,1);

for i = 1:N
    g = grades(i);  % 0-indexed grade

    % 인구학적 특성
    age(i) = max(25, min(85, normrnd(55, 12)));
    sex(i) = randi([0, 1]);
    if sex(i) == 0
        bsa(i) = normrnd(1.7, 0.15);
    else
        bsa(i) = normrnd(1.9, 0.15);
    end

    % DOX 누적 용량
    dox_dose(i) = dox_ranges(g+1,1) + rand() * (dox_ranges(g+1,2) - dox_ranges(g+1,1));

    % Ees (수축력)
    ees_arr(i) = ees_ranges(g+1,1) + rand() * (ees_ranges(g+1,2) - ees_ranges(g+1,1));
    ees_arr(i) = ees_arr(i) + normrnd(0, 0.05);
    ees_arr(i) = max(0.4, min(3.5, ees_arr(i)));

    % 기타 파라미터
    edv_arr(i) = max(80, min(200, 120 + g*12 + normrnd(0, 8)));
    aop_arr(i) = max(60, min(160, 100 + normrnd(0, 8)));
    hr_arr(i)  = max(50, min(140, 72 + g*8 + normrnd(0, 6)));
    bedp_arr(i) = max(0.015, min(0.06, 0.028 + g*0.004 + normrnd(0, 0.002)));

    % 혈역학 계산
    hemo = calc_hemodynamics(edv_arr(i), aop_arr(i), ees_arr(i), ...
                             hr_arr(i), bedp_arr(i), V0, A_EDP);
    EDV_out(i) = hemo.EDV; ESV_out(i) = hemo.ESV; SV_out(i) = hemo.SV;
    EF_out(i)  = hemo.EF;  CO_out(i)  = hemo.CO;  EDP_out(i) = hemo.EDP;
    ESP_out(i) = hemo.ESP;  Peak_LVP_out(i) = hemo.Peak_LVP; SW_out(i) = hemo.SW;
    Ees_out(i) = ees_arr(i);

    % 바이오마커
    troponin(i) = 0.02 + g*0.15 + exprnd(0.05);
    bnp_arr(i)  = 50 + g*120 + exprnd(30);
    gls_arr(i)  = -20 + g*3.5 + normrnd(0, 1.5);
end

% 테이블 생성
T = table(patient_id, age, sex, bsa, dox_dose, grades, ...
          EDV_out, ESV_out, SV_out, EF_out, CO_out, EDP_out, ESP_out, ...
          Peak_LVP_out, SW_out, Ees_out, hr_arr, bedp_arr, ...
          troponin, bnp_arr, gls_arr, ...
          'VariableNames', {'PatientID','Age','Sex','BSA','DOX_Dose','Grade', ...
          'EDV','ESV','SV','EF','CO','EDP','ESP','Peak_LVP','SW','Ees','HR','BEDP', ...
          'Troponin','BNP','GLS'});

fprintf('\n[데이터셋] SynCardioTox-1K\n');
fprintf('  총 표본 수: %d명\n', N);
fprintf('  연령: %.1f ± %.1f세\n', mean(T.Age), std(T.Age));
fprintf('  남성: %d명 (%.1f%%)\n', sum(T.Sex==1), sum(T.Sex==1)/N*100);
fprintf('\n  심독성 등급 분포:\n');
for g = 0:3
    idx = T.Grade == g;
    fprintf('    Grade %d (%s): %d명 | Ees=%.2f±%.2f | EF=%.1f±%.1f%%\n', ...
        g, grade_names{g+1}, sum(idx), mean(T.Ees(idx)), std(T.Ees(idx)), ...
        mean(T.EF(idx)), std(T.EF(idx)));
end

%% =====================================================================
%  STEP 3: 특징 추출 (Feature Engineering)
%  =====================================================================
fprintf('\n'); fprintf('=' .* ones(1,70)); fprintf('\n');
fprintf('  STEP 3: 특징 추출 (Feature Engineering)\n');
fprintf('=' .* ones(1,70)); fprintf('\n');

% 파생 특징
T.SV_index     = T.SV ./ T.BSA;
T.CO_index     = T.CO ./ T.BSA;
T.EDP_EDV_ratio = T.EDP ./ T.EDV;
T.SW_EDV_ratio  = T.SW ./ T.EDV;
T.HR_SV_product = T.HR .* T.SV;

feature_names = {'Age','Sex','BSA','DOX_Dose', ...
                 'EDV','ESV','SV','EF','CO','EDP','Peak_LVP','SW', ...
                 'HR','Troponin','BNP','GLS', ...
                 'SV_index','CO_index','EDP_EDV_ratio','SW_EDV_ratio','HR_SV_product'};

X = T{:, feature_names};
y_class = T.Grade;
y_ees   = T.Ees;

fprintf('\n[특징 벡터] 총 %d개 특징\n', length(feature_names));

%% =====================================================================
%  STEP 4: 모델 학습 (Model Training)
%  =====================================================================
fprintf('\n'); fprintf('=' .* ones(1,70)); fprintf('\n');
fprintf('  STEP 4: 모델 학습\n');
fprintf('=' .* ones(1,70)); fprintf('\n');

% Train/Test Split (80/20, stratified)
cv = cvpartition(y_class, 'HoldOut', 0.2, 'Stratify', true);
X_train = X(training(cv), :);  X_test = X(test(cv), :);
y_train_c = y_class(training(cv));  y_test_c = y_class(test(cv));
y_train_r = y_ees(training(cv));    y_test_r = y_ees(test(cv));

fprintf('\n[데이터 분할] Train %d / Test %d\n', size(X_train,1), size(X_test,1));

% --- Task A: 심독성 등급 분류 (Random Forest = TreeBagger) ---
fprintf('\n--- Task A: 심독성 등급 분류 (TreeBagger) ---\n');
nTrees = 200;
rf_model = TreeBagger(nTrees, X_train, y_train_c, ...
    'Method', 'classification', ...
    'MaxNumSplits', 100, ...
    'MinLeafSize', 3, ...
    'OOBPredictorImportance', 'on', ...
    'NumPredictorsToSample', 'all');

% 5-Fold Cross Validation
cv5 = cvpartition(y_train_c, 'KFold', 5, 'Stratify', true);
cv_accs = zeros(5, 1);
for k = 1:5
    rf_k = TreeBagger(nTrees, X_train(training(cv5,k),:), ...
                      y_train_c(training(cv5,k)), ...
                      'Method', 'classification', 'MinLeafSize', 3);
    pred_k = str2double(predict(rf_k, X_train(test(cv5,k),:)));
    cv_accs(k) = mean(pred_k == y_train_c(test(cv5,k)));
end
fprintf('  5-Fold CV Accuracy: %.3f ± %.3f\n', mean(cv_accs), std(cv_accs));

% Test set 예측
[y_pred_c_str, y_pred_proba] = predict(rf_model, X_test);
y_pred_c = str2double(y_pred_c_str);
test_acc = mean(y_pred_c == y_test_c);
fprintf('  Test Accuracy: %.3f\n', test_acc);

% Multiclass AUC (One-vs-Rest)
auc_values = zeros(4, 1);
for g = 0:3
    binary_true = double(y_test_c == g);
    prob_g = y_pred_proba(:, g+1);
    [fpr_g, tpr_g, ~] = perfcurve(binary_true, prob_g, 1);
    auc_values(g+1) = trapz(fpr_g, tpr_g);
end
auc_macro = mean(auc_values);
fprintf('  Test AUC (macro OVR): %.3f\n', auc_macro);

% --- Task B: Ees 회귀 추정 (Ensemble of Regression Trees) ---
fprintf('\n--- Task B: Ees 회귀 추정 (Ensemble Regression Trees) ---\n');
gb_model = fitrensemble(X_train, y_train_r, ...
    'Method', 'LSBoost', ...
    'NumLearningCycles', 200, ...
    'Learners', templateTree('MaxNumSplits', 63), ...
    'LearnRate', 0.1);

y_pred_r = predict(gb_model, X_test);
mae = mean(abs(y_test_r - y_pred_r));
ss_res = sum((y_test_r - y_pred_r).^2);
ss_tot = sum((y_test_r - mean(y_test_r)).^2);
r2 = 1 - ss_res / ss_tot;
fprintf('  MAE: %.4f mmHg/mL\n', mae);
fprintf('  R²: %.4f\n', r2);

%% =====================================================================
%  STEP 5: 특징 중요도 분석
%  =====================================================================
fprintf('\n'); fprintf('=' .* ones(1,70)); fprintf('\n');
fprintf('  STEP 5: 특징 중요도 분석\n');
fprintf('=' .* ones(1,70)); fprintf('\n');

importance = rf_model.OOBPermutedPredictorDeltaError;
[imp_sorted, imp_idx] = sort(importance, 'descend');

fprintf('\n[분류 모델 Feature Importance - Top 10]\n');
for k = 1:min(10, length(imp_sorted))
    fprintf('  %-22s %.4f  %s\n', feature_names{imp_idx(k)}, ...
            imp_sorted(k), repmat('█', 1, round(imp_sorted(k)/max(imp_sorted)*30)));
end

%% =====================================================================
%  STEP 6: 시각화 (12-Panel Figure)
%  =====================================================================
fprintf('\n'); fprintf('=' .* ones(1,70)); fprintf('\n');
fprintf('  STEP 6: 시각화\n');
fprintf('=' .* ones(1,70)); fprintf('\n');

colors = [45/255 212/255 191/255;   % Normal  - teal
          74/255 123/255 255/255;   % Mild    - blue
          255/255 169/255 77/255;   % Moderate - orange
          255/255 107/255 107/255]; % Severe  - coral

fig = figure('Position', [50 50 1600 1800], 'Color', 'w');
sgtitle('AI-Based Cardiotoxicity Quantification via PV Loop Analysis', ...
        'FontSize', 16, 'FontWeight', 'bold');

% 6-1: PV Loops by Grade
subplot(4,3,1); hold on;
for g = 0:3
    idx_g = find(T.Grade == g);
    sample_idx = idx_g(randperm(length(idx_g), min(5, length(idx_g))));
    for j = 1:length(sample_idx)
        ii = sample_idx(j);
        edv_v = T.EDV(ii); esv_v = T.ESV(ii);
        edp_v = T.EDP(ii); aop_v = 100; esp_v = T.ESP(ii);
        plvp_v = T.Peak_LVP(ii); bedp_v = T.BEDP(ii);
        % Simplified PV loop
        v_fill = linspace(esv_v, edv_v, 30);
        p_fill = arrayfun(@(v) edpvr_func(v, bedp_v, V0, A_EDP), v_fill);
        v_isov1 = edv_v * ones(1,20);
        p_isov1 = linspace(edp_v, aop_v, 20);
        v_eject = linspace(edv_v, esv_v, 30);
        p_eject = linspace(aop_v, esp_v, 30) + sin(linspace(0,pi,30)) .* (plvp_v - aop_v) * 0.5;
        v_isov2 = esv_v * ones(1,20);
        p_isov2 = linspace(esp_v, edpvr_func(esv_v, bedp_v, V0, A_EDP), 20);
        plot([v_fill v_isov1 v_eject v_isov2], [p_fill p_isov1 p_eject p_isov2], ...
             'Color', [colors(g+1,:) 0.4], 'LineWidth', 0.8);
    end
end
% ESPVR lines
ees_demo = [2.5, 1.75, 1.25, 0.75];
v_line = linspace(V0, 80, 50);
for g = 0:3
    plot(v_line, ees_demo(g+1) .* (v_line - V0), '--', 'Color', colors(g+1,:), 'LineWidth', 1.5);
end
xlabel('Volume (mL)'); ylabel('Pressure (mmHg)');
title('PV Loops by Toxicity Grade', 'FontWeight', 'bold');
xlim([0 200]); ylim([0 200]);
legend(grade_names, 'Location', 'northwest', 'FontSize', 7); hold off;

% 6-2: Frank-Starling Curves
subplot(4,3,2); hold on;
edv_range = linspace(60, 200, 100);
for g = 0:3
    ees_v = ees_demo(g+1);
    sv_v = max(edv_range - min(V0 + 100/ees_v, edv_range - 2), 0);
    plot(edv_range, sv_v, 'Color', colors(g+1,:), 'LineWidth', 2.5);
end
xlabel('EDV (mL)'); ylabel('SV (mL)');
title('Frank-Starling Curves', 'FontWeight', 'bold');
legend(grade_names, 'Location', 'northwest'); xlim([60 200]); ylim([0 160]); hold off;

% 6-3: Ees Distribution by Grade
subplot(4,3,3); hold on;
edges = linspace(0.3, 3.5, 30);
for g = 0:3
    histogram(T.Ees(T.Grade==g), edges, 'FaceColor', colors(g+1,:), ...
              'FaceAlpha', 0.6, 'EdgeColor', 'w');
end
xlabel('Ees (mmHg/mL)'); ylabel('Count');
title('Ees Distribution by Grade', 'FontWeight', 'bold');
legend(grade_names); hold off;

% 6-4: Confusion Matrix
subplot(4,3,4);
cm = confusionmat(y_test_c, y_pred_c);
confusionchart(cm, grade_names, 'Title', sprintf('Confusion Matrix (Acc=%.3f)', test_acc));

% 6-5: ROC Curves
subplot(4,3,5); hold on;
for g = 0:3
    binary_true = double(y_test_c == g);
    prob_g = y_pred_proba(:, g+1);
    [fpr_g, tpr_g, ~] = perfcurve(binary_true, prob_g, 1);
    plot(fpr_g, tpr_g, 'Color', colors(g+1,:), 'LineWidth', 2);
end
plot([0 1], [0 1], 'k--', 'LineWidth', 0.5);
xlabel('FPR'); ylabel('TPR');
title(sprintf('ROC Curves (Macro AUC=%.3f)', auc_macro), 'FontWeight', 'bold');
legend([strcat(grade_names', arrayfun(@(a) sprintf(' (AUC=%.3f)', a), auc_values, 'Uni', false)), {'Chance'}], ...
       'Location', 'southeast', 'FontSize', 7);
hold off;

% 6-6: Feature Importance (Top 12)
subplot(4,3,6);
top_k = min(12, length(imp_sorted));
barh(1:top_k, imp_sorted(1:top_k), 'FaceColor', [74/255 123/255 255/255]);
set(gca, 'YTick', 1:top_k, 'YTickLabel', feature_names(imp_idx(1:top_k)));
set(gca, 'YDir', 'reverse');
xlabel('Importance'); title('Feature Importance (Top 12)', 'FontWeight', 'bold');

% 6-7: Ees Regression (True vs Predicted)
subplot(4,3,7); hold on;
for g = 0:3
    mask = y_test_c == g;
    scatter(y_test_r(mask), y_pred_r(mask), 20, colors(g+1,:), 'filled', 'MarkerFaceAlpha', 0.6);
end
plot([0 3.5], [0 3.5], 'k--', 'LineWidth', 0.5);
xlabel('True Ees'); ylabel('Predicted Ees');
title(sprintf('Ees Regression (R²=%.3f, MAE=%.3f)', r2, mae), 'FontWeight', 'bold');
legend(grade_names, 'FontSize', 7); hold off;

% 6-8: EF vs Ees
subplot(4,3,8); hold on;
for g = 0:3
    idx_g = T.Grade == g;
    scatter(T.Ees(idx_g), T.EF(idx_g), 15, colors(g+1,:), 'filled', 'MarkerFaceAlpha', 0.5);
end
yline(40, 'r--', 'EF=40% (HFrEF)', 'LineWidth', 1, 'Alpha', 0.5);
xlabel('Ees (mmHg/mL)'); ylabel('EF (%)');
title('EF vs Ees by Grade', 'FontWeight', 'bold');
legend(grade_names, 'FontSize', 7); hold off;

% 6-9: DOX Dose vs Ees
subplot(4,3,9); hold on;
for g = 0:3
    idx_g = T.Grade == g;
    scatter(T.DOX_Dose(idx_g), T.Ees(idx_g), 15, colors(g+1,:), 'filled', 'MarkerFaceAlpha', 0.5);
end
xlabel('DOX Cumulative Dose (mg/m²)'); ylabel('Ees (mmHg/mL)');
title('DOX Dose vs Contractility', 'FontWeight', 'bold');
legend(grade_names, 'FontSize', 7); hold off;

% 6-10: Troponin by Grade
subplot(4,3,10);
boxplot_data = cell(4,1);
for g = 0:3
    boxplot_data{g+1} = T.Troponin(T.Grade == g);
end
max_len = max(cellfun(@length, boxplot_data));
bp_matrix = NaN(max_len, 4);
for g = 1:4
    bp_matrix(1:length(boxplot_data{g}), g) = boxplot_data{g};
end
boxplot(bp_matrix, 'Labels', grade_names, 'Colors', colors);
ylabel('Troponin (ng/mL)');
title('Troponin by Grade', 'FontWeight', 'bold');

% 6-11: GLS by Grade
subplot(4,3,11);
gls_data = cell(4,1);
for g = 0:3
    gls_data{g+1} = T.GLS(T.Grade == g);
end
bp_matrix2 = NaN(max_len, 4);
for g = 1:4
    bp_matrix2(1:length(gls_data{g}), g) = gls_data{g};
end
boxplot(bp_matrix2, 'Labels', grade_names, 'Colors', colors);
ylabel('GLS (%)');
title('GLS by Grade', 'FontWeight', 'bold');
yline(-15, 'r--', 'GLS=-15%', 'Alpha', 0.5);

% 6-12: Model Architecture (Text)
subplot(4,3,12); axis off;
arch_text = {
    '┌────────────────────────────────┐'
    '│      MODEL ARCHITECTURE        │'
    '├────────────────────────────────┤'
    '│  INPUT (21 features)           │'
    '│   ├ Demographics (3)           │'
    '│   ├ Drug history (1)           │'
    '│   ├ PV hemodynamics (8)        │'
    '│   ├ Heart rate (1)             │'
    '│   ├ Biomarkers (3)             │'
    '│   └ Derived features (5)       │'
    '│          ↓                     │'
    '│  ┌───────────────────┐         │'
    '│  │ TreeBagger (200)  │→ Grade  │'
    '│  │ LSBoost Ensemble  │→ Ees    │'
    '│  └───────────────────┘         │'
    '│          ↓                     │'
    '│  OUTPUT                        │'
    '│   ├ Toxicity Grade (0-3)       │'
    '│   ├ Ees estimate (mmHg/mL)     │'
    '│   └ Risk probability           │'
    '└────────────────────────────────┘'
};
text(0.05, 0.95, arch_text, 'FontName', 'FixedWidth', 'FontSize', 8, ...
     'VerticalAlignment', 'top', 'BackgroundColor', [0.94 0.96 1.0], ...
     'EdgeColor', [74/255 123/255 255/255], 'Margin', 8);

% 저장
saveas(fig, 'cardiotoxicity_ai_results_matlab.png');
fprintf('\n[시각화] cardiotoxicity_ai_results_matlab.png 저장 완료\n');

%% =====================================================================
%  STEP 7: 데이터 저장 & 요약
%  =====================================================================
fprintf('\n'); fprintf('=' .* ones(1,70)); fprintf('\n');
fprintf('  STEP 7: 요약\n');
fprintf('=' .* ones(1,70)); fprintf('\n');

writetable(T, 'synth_cardiotox_dataset_matlab.csv');
fprintf('\n[데이터셋] synth_cardiotox_dataset_matlab.csv 저장 완료\n');

fprintf('\n╔═══════════════════════════════════════════════════════════╗\n');
fprintf('║       AI 심근독성 정량 모델 최종 요약 (MATLAB)           ║\n');
fprintf('╠═══════════════════════════════════════════════════════════╣\n');
fprintf('║  데이터셋: SynCardioTox-1K (%d명)                      ║\n', N);
fprintf('║  Task A: Classification (TreeBagger)                     ║\n');
fprintf('║    5-Fold CV: %.3f ± %.3f                              ║\n', mean(cv_accs), std(cv_accs));
fprintf('║    Test Accuracy: %.3f                                   ║\n', test_acc);
fprintf('║    Test AUC (macro): %.3f                                ║\n', auc_macro);
fprintf('║  Task B: Ees Regression (LSBoost)                        ║\n');
fprintf('║    MAE: %.4f mmHg/mL                                    ║\n', mae);
fprintf('║    R²: %.4f                                              ║\n', r2);
fprintf('╚═══════════════════════════════════════════════════════════╝\n');
fprintf('\n모든 단계 완료!\n');

%% =====================================================================
%  로컬 함수 정의
%  =====================================================================

function p = edpvr_func(v, bedp, V0, A_EDP)
    % 이완기말 압력-용적 관계
    if v <= V0
        p = 0;
    else
        p = A_EDP * (exp(bedp * (v - V0)) - 1);
    end
end

function hemo = calc_hemodynamics(edv, aop, ees, hr, bedp, V0, A_EDP)
    % 혈역학 계산
    edp = A_EDP * (exp(bedp * (edv - V0)) - 1);
    if edv <= V0; edp = 0; end

    esv = V0 + aop / ees;
    esv = max(V0 + 1, min(edv - 2, esv));
    sv = edv - esv;
    ef = (sv / edv) * 100;
    co = (sv * hr) / 1000;
    esp = ees * (esv - V0);
    peak_lvp = aop + (ees * (edv - V0) - aop) * 0.15 + 15;
    peak_lvp = max(peak_lvp, aop + 10);
    sw = sv * (aop + esp) / 2;

    hemo.EDV = edv; hemo.ESV = esv; hemo.SV = sv;
    hemo.EF = ef; hemo.CO = co; hemo.EDP = edp;
    hemo.ESP = esp; hemo.Peak_LVP = peak_lvp; hemo.SW = sw;
    hemo.Ees = ees; hemo.AoP = aop; hemo.HR = hr; hemo.BEDP = bedp;
end
