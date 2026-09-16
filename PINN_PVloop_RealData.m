%% =========================================================================
%  Physics-Informed Neural Network (PINN) 기반
%  PV 루프 심기능 평가 파이프라인 — 실제 임상 데이터 활용
%
%  데이터: UCI Heart Failure Clinical Records (Chicco & Jurman, 2020)
%    - 299명 심부전 환자, 13개 임상 변수, 사망 여부 (DEATH_EVENT)
%    - CC BY 4.0 라이선스
%    - https://archive.ics.uci.edu/dataset/519/heart+failure+clinical+records
%
%  핵심 아이디어:
%    실제 EF(%) 데이터 → 생리학 모델로 PV 루프 파라미터 역추정(Ees, ESV, SV 등)
%    → 혈역학 파생 특징 + 원본 임상 변수 → ML 모델 (사망 예측 + Ees 회귀)
%    → PINN 개념: 물리법칙(ESPVR/EDPVR)이 특징 추출 단계에 내장됨
%
%  순천향대학교 의과대학 | 심장 및 순환생리 실습
%  2026년 4월
%
%  Required: Statistics and Machine Learning Toolbox
%  =========================================================================
close all; clear; clc;

fprintf('╔═══════════════════════════════════════════════════════════════╗\n');
fprintf('║  PINN 기반 PV 루프 심기능 평가 — 실제 임상 데이터 활용      ║\n');
fprintf('║  UCI Heart Failure Clinical Records (N=299)                  ║\n');
fprintf('╚═══════════════════════════════════════════════════════════════╝\n\n');

%% =====================================================================
%  STEP 1: 실제 데이터 로드 & 탐색
%  =====================================================================
fprintf('=== STEP 1: 데이터 로드 ===\n');

T = readtable('heart_failure_clinical_records.csv');
N = height(T);
fprintf('  로드 완료: %d명 환자, %d개 변수\n', N, width(T));
fprintf('  변수: %s\n', strjoin(T.Properties.VariableNames, ', '));

% 기본 통계
fprintf('\n  [인구 특성]\n');
fprintf('    연령: %.1f ± %.1f세 (범위: %.0f–%.0f)\n', ...
    mean(T.age), std(T.age), min(T.age), max(T.age));
fprintf('    남성: %d명 (%.1f%%)\n', sum(T.sex==1), sum(T.sex==1)/N*100);
fprintf('    당뇨: %d명 (%.1f%%)\n', sum(T.diabetes==1), sum(T.diabetes==1)/N*100);
fprintf('    빈혈: %d명 (%.1f%%)\n', sum(T.anaemia==1), sum(T.anaemia==1)/N*100);
fprintf('    고혈압: %d명 (%.1f%%)\n', sum(T.high_blood_pressure==1), sum(T.high_blood_pressure==1)/N*100);
fprintf('    흡연: %d명 (%.1f%%)\n', sum(T.smoking==1), sum(T.smoking==1)/N*100);

fprintf('\n  [심기능]\n');
fprintf('    EF: %.1f ± %.1f%% (범위: %d–%d%%)\n', ...
    mean(T.ejection_fraction), std(T.ejection_fraction), ...
    min(T.ejection_fraction), max(T.ejection_fraction));

fprintf('\n  [예후]\n');
fprintf('    사망: %d명 (%.1f%%)\n', sum(T.DEATH_EVENT==1), sum(T.DEATH_EVENT==1)/N*100);
fprintf('    생존: %d명 (%.1f%%)\n', sum(T.DEATH_EVENT==0), sum(T.DEATH_EVENT==0)/N*100);

%% =====================================================================
%  STEP 2: 생리학 모델 — EF로부터 PV 루프 파라미터 역추정
%  "Physics-Informed" 특징 추출
%  =====================================================================
fprintf('\n=== STEP 2: Physics-Informed 특징 추출 (EF → PV 루프 역추정) ===\n');

% 생리학 상수 (Guyton Ch.9 + Burkhoff 2005)
V0    = 10;       % Dead volume (mL)
A_EDP = 0.337;    % EDPVR scaling (mmHg)
AoP_default = 100; % 평균 대동맥압 가정 (mmHg)

% HF 심부전 등급 (ESC 2021 가이드라인)
%   HFrEF: EF < 40%   → 심한 수축기능 저하
%   HFmrEF: 40-49%    → 경도 수축기능 저하
%   HFpEF: EF ≥ 50%   → 보존 수축기능
hf_class = zeros(N, 1);
hf_class(T.ejection_fraction < 40)  = 2;  % HFrEF (Severe)
hf_class(T.ejection_fraction >= 40 & T.ejection_fraction < 50) = 1;  % HFmrEF (Moderate)
hf_class(T.ejection_fraction >= 50) = 0;  % HFpEF (Mild/Normal)
hf_names = {'HFpEF', 'HFmrEF', 'HFrEF'};

T.HF_class = hf_class;

fprintf('  심부전 분류 (ESC 2021):\n');
for c = 0:2
    fprintf('    %s (class %d): %d명 (%.1f%%)\n', ...
        hf_names{c+1}, c, sum(hf_class==c), sum(hf_class==c)/N*100);
end

% --- PV 루프 파라미터 역추정 ---
% EF = SV/EDV × 100
% 가정: EDV는 EF와 고혈압/연령에 따라 추정
%   정상 EDV ≈ 120 mL, 심부전 시 확장 (EF 낮을수록 EDV 높음)
%   Burkhoff 2005: EDV = V0 + AoP/Ees + AoP/(Ees × EF/100 - 1) 근사
%   단순화: EDV ≈ 120 + (60 - EF) × 1.5 (EF 기반 보상적 확장 모델)

EF_pct = T.ejection_fraction;

% EDV 추정 (EF 기반 + 연령 보정 + 고혈압 보정)
EDV_est = 120 + (55 - EF_pct) .* 1.8 ...    % EF 기반 보상 확장
        + (T.age - 55) .* 0.3 ...             % 연령 보정 (노화 → 경직)
        + T.high_blood_pressure .* 8;          % 고혈압 → 추가 확장
EDV_est = max(80, min(250, EDV_est));          % 생리학적 범위 제한

% ESV = EDV × (1 - EF/100)
ESV_est = EDV_est .* (1 - EF_pct/100);
ESV_est = max(V0 + 5, ESV_est);

% SV = EDV - ESV
SV_est = EDV_est - ESV_est;

% Ees 역추정: ESPVR에서 Ees = AoP / (ESV - V0)
% 고혈압 환자는 AoP 보정
AoP_est = AoP_default + T.high_blood_pressure .* 15 + (T.age - 55) .* 0.2;
AoP_est = max(70, min(160, AoP_est));

Ees_est = AoP_est ./ (ESV_est - V0);
Ees_est = max(0.3, min(5.0, Ees_est));

% EDPVR: EDP = A × (exp(B × (EDV - V0)) - 1)
% B_edp: 정상 0.028, 심부전 시 경직도 증가
B_edp_est = 0.028 + (2 - hf_class) .* (-0.003) ...  % HFrEF는 유순도↑(확장)
          + T.high_blood_pressure .* 0.004 ...         % 고혈압 → 경직↑
          + (T.age - 55) .* 0.0002;                    % 연령 → 경직↑
B_edp_est = max(0.015, min(0.06, B_edp_est));

EDP_est = A_EDP .* (exp(B_edp_est .* (EDV_est - V0)) - 1);
EDP_est = max(2, min(40, EDP_est));

% HR 추정 (CO 기반 — 실제 데이터에는 HR 없음)
% CO 정상 ≈ 5 L/min → HR = CO/SV × 1000
% 심부전 시 보상성 빈맥
HR_est = 72 + (2 - Ees_est) .* 12 + (T.age - 55) .* 0.15;
HR_est = max(50, min(130, HR_est));

% CO
CO_est = SV_est .* HR_est / 1000;

% ESP
ESP_est = Ees_est .* (ESV_est - V0);

% Stroke Work (근사: 사다리꼴)
SW_est = SV_est .* (AoP_est + ESP_est) / 2;

% 파생 특징 테이블에 추가
T.EDV_est     = round(EDV_est, 1);
T.ESV_est     = round(ESV_est, 1);
T.SV_est      = round(SV_est, 1);
T.Ees_est     = round(Ees_est, 3);
T.EDP_est     = round(EDP_est, 1);
T.HR_est      = round(HR_est, 0);
T.CO_est      = round(CO_est, 2);
T.ESP_est     = round(ESP_est, 1);
T.SW_est      = round(SW_est, 0);
T.AoP_est     = round(AoP_est, 0);
T.B_edp_est   = round(B_edp_est, 4);

fprintf('\n  [역추정 PV 파라미터 요약]\n');
fprintf('    EDV: %.1f ± %.1f mL\n', mean(EDV_est), std(EDV_est));
fprintf('    ESV: %.1f ± %.1f mL\n', mean(ESV_est), std(ESV_est));
fprintf('    SV:  %.1f ± %.1f mL\n', mean(SV_est), std(SV_est));
fprintf('    Ees: %.2f ± %.2f mmHg/mL\n', mean(Ees_est), std(Ees_est));
fprintf('    EDP: %.1f ± %.1f mmHg\n', mean(EDP_est), std(EDP_est));
fprintf('    CO:  %.1f ± %.1f L/min\n', mean(CO_est), std(CO_est));

% 등급별 Ees 검증
fprintf('\n  [등급별 Ees 검증]\n');
for c = 0:2
    idx = hf_class == c;
    fprintf('    %s: Ees = %.2f ± %.2f, EF = %.1f ± %.1f%%\n', ...
        hf_names{c+1}, mean(Ees_est(idx)), std(Ees_est(idx)), ...
        mean(EF_pct(idx)), std(EF_pct(idx)));
end

%% =====================================================================
%  STEP 3: 특징 벡터 구성
%  =====================================================================
fprintf('\n=== STEP 3: 특징 벡터 구성 ===\n');

% 원본 임상 변수 + PV 루프 역추정 변수 + 파생 변수
T.SV_index     = T.SV_est ./ (1.7 + 0.2 * T.sex);    % BSA 근사 보정
T.CO_index     = T.CO_est ./ (1.7 + 0.2 * T.sex);
T.EDP_EDV_ratio = T.EDP_est ./ T.EDV_est;
T.SW_EDV_ratio  = T.SW_est ./ T.EDV_est;
T.CPK_log       = log10(T.creatinine_phosphokinase + 1);  % 로그 변환 (skewed)
T.Cr_log        = log10(T.serum_creatinine + 0.1);

feature_names = {
    % 원본 임상 (10개)
    'age', 'anaemia', 'CPK_log', 'diabetes', ...
    'ejection_fraction', 'high_blood_pressure', ...
    'serum_creatinine', 'serum_sodium', 'sex', 'smoking', ...
    % PV 루프 역추정 (8개)
    'EDV_est', 'ESV_est', 'SV_est', 'Ees_est', ...
    'EDP_est', 'CO_est', 'ESP_est', 'SW_est', ...
    % 파생 (4개)
    'SV_index', 'CO_index', 'EDP_EDV_ratio', 'SW_EDV_ratio'
};

X = T{:, feature_names};
y_death = T.DEATH_EVENT;         % 이진 분류 타겟
y_hf    = T.HF_class;            % 3-class 분류 타겟
y_ees   = T.Ees_est;             % 회귀 타겟

fprintf('  특징 수: %d개 (원본 임상 10 + PV역추정 8 + 파생 4)\n', length(feature_names));
fprintf('  표본 수: %d명\n', N);

%% =====================================================================
%  STEP 4: 모델 학습
%  =====================================================================
fprintf('\n=== STEP 4: 모델 학습 ===\n');

% --- 4A: 사망 예측 (Binary Classification) ---
fprintf('\n--- Task A: 사망 예측 (Mortality Prediction) ---\n');

rng(42);
cv_part = cvpartition(y_death, 'HoldOut', 0.2, 'Stratify', true);
X_train = X(training(cv_part), :);  X_test = X(test(cv_part), :);
y_train_d = y_death(training(cv_part));  y_test_d = y_death(test(cv_part));
y_train_h = y_hf(training(cv_part));     y_test_h = y_hf(test(cv_part));
y_train_e = y_ees(training(cv_part));    y_test_e = y_ees(test(cv_part));

fprintf('  Train: %d명, Test: %d명\n', sum(training(cv_part)), sum(test(cv_part)));
fprintf('  Test 사망률: %.1f%%\n', sum(y_test_d==1)/length(y_test_d)*100);

% Random Forest (사망 예측)
nTrees = 200;
rf_death = TreeBagger(nTrees, X_train, y_train_d, ...
    'Method', 'classification', ...
    'MinLeafSize', 3, ...
    'OOBPredictorImportance', 'on', ...
    'Cost', [0 2; 1 0]);  % 사망 예측 비용 비대칭 (False Negative 패널티)

[pred_d_str, pred_d_prob] = predict(rf_death, X_test);
pred_d = str2double(pred_d_str);
acc_death = mean(pred_d == y_test_d);

% AUC
[fpr_d, tpr_d, ~, auc_death] = perfcurve(y_test_d, pred_d_prob(:,2), 1);
fprintf('  Accuracy: %.3f\n', acc_death);
fprintf('  AUC: %.3f\n', auc_death);

% Sensitivity / Specificity
tp = sum(pred_d==1 & y_test_d==1);
tn = sum(pred_d==0 & y_test_d==0);
fp = sum(pred_d==1 & y_test_d==0);
fn = sum(pred_d==0 & y_test_d==1);
sensitivity = tp / (tp + fn);
specificity = tn / (tn + fp);
fprintf('  Sensitivity: %.3f\n', sensitivity);
fprintf('  Specificity: %.3f\n', specificity);

% 5-Fold CV
cv5 = cvpartition(y_train_d, 'KFold', 5, 'Stratify', true);
cv_accs = zeros(5,1);
cv_aucs = zeros(5,1);
for k = 1:5
    rf_k = TreeBagger(nTrees, X_train(training(cv5,k),:), ...
                      y_train_d(training(cv5,k)), ...
                      'Method', 'classification', 'MinLeafSize', 3);
    [p_str, p_prob] = predict(rf_k, X_train(test(cv5,k),:));
    p_k = str2double(p_str);
    cv_accs(k) = mean(p_k == y_train_d(test(cv5,k)));
    [~,~,~,cv_aucs(k)] = perfcurve(y_train_d(test(cv5,k)), p_prob(:,2), 1);
end
fprintf('  5-Fold CV Accuracy: %.3f ± %.3f\n', mean(cv_accs), std(cv_accs));
fprintf('  5-Fold CV AUC: %.3f ± %.3f\n', mean(cv_aucs), std(cv_aucs));

% --- 4B: HF 등급 분류 (3-class) ---
fprintf('\n--- Task B: 심부전 등급 분류 (HFpEF/HFmrEF/HFrEF) ---\n');

rf_hf = TreeBagger(nTrees, X_train, y_train_h, ...
    'Method', 'classification', ...
    'MinLeafSize', 3, ...
    'OOBPredictorImportance', 'on');

[pred_h_str, pred_h_prob] = predict(rf_hf, X_test);
pred_h = str2double(pred_h_str);
acc_hf = mean(pred_h == y_test_h);
fprintf('  Accuracy: %.3f\n', acc_hf);

% --- 4C: Ees 회귀 추정 ---
fprintf('\n--- Task C: Ees 회귀 추정 (LSBoost) ---\n');

gb_ees = fitrensemble(X_train, y_train_e, ...
    'Method', 'LSBoost', ...
    'NumLearningCycles', 200, ...
    'Learners', templateTree('MaxNumSplits', 31), ...
    'LearnRate', 0.1);

pred_e = predict(gb_ees, X_test);
mae_ees = mean(abs(y_test_e - pred_e));
ss_res = sum((y_test_e - pred_e).^2);
ss_tot = sum((y_test_e - mean(y_test_e)).^2);
r2_ees = 1 - ss_res / ss_tot;
fprintf('  MAE: %.4f mmHg/mL\n', mae_ees);
fprintf('  R²: %.4f\n', r2_ees);

%% =====================================================================
%  STEP 5: Feature Importance 분석
%  =====================================================================
fprintf('\n=== STEP 5: Feature Importance ===\n');

imp_death = rf_death.OOBPermutedPredictorDeltaError;
[imp_sorted, imp_idx] = sort(imp_death, 'descend');

fprintf('\n  [사망 예측 모델 — Top 10 Features]\n');
for k = 1:min(10, length(imp_sorted))
    bar_len = max(1, round(imp_sorted(k)/max(imp_sorted)*25));
    fprintf('    %-20s %.4f  %s\n', feature_names{imp_idx(k)}, ...
            imp_sorted(k), repmat('#', 1, bar_len));
end

%% =====================================================================
%  STEP 6: 종합 시각화 (12-Panel)
%  =====================================================================
fprintf('\n=== STEP 6: 시각화 ===\n');

colors3 = [45/255 212/255 191/255;    % HFpEF  - teal
           255/255 169/255 77/255;    % HFmrEF - orange
           255/255 107/255 107/255];  % HFrEF  - coral
colors2 = [74/255 123/255 255/255;    % Survived - blue
           255/255 107/255 107/255];  % Died     - coral

fig = figure('Position', [30 30 1700 1900], 'Color', 'w');
sgtitle({'PINN 기반 PV 루프 심기능 평가 — UCI Heart Failure (N=299)', ...
         'Physics-Informed Feature Extraction + Random Forest / Gradient Boosting'}, ...
         'FontSize', 15, 'FontWeight', 'bold');

% 6-1: PV Loops (역추정) by HF Class
subplot(4,3,1); hold on;
for c = 0:2
    idx = find(T.HF_class == c);
    sample = idx(randperm(length(idx), min(8, length(idx))));
    for j = 1:length(sample)
        ii = sample(j);
        edv = T.EDV_est(ii); esv = T.ESV_est(ii);
        edp = T.EDP_est(ii); aop = T.AoP_est(ii); esp = T.ESP_est(ii);
        bedp = T.B_edp_est(ii);
        plvp = aop + (T.Ees_est(ii)*(edv-V0) - aop)*0.15 + 15;
        % PV loop trace
        v_fill = linspace(esv, edv, 30);
        p_fill = A_EDP .* (exp(bedp .* (v_fill - V0)) - 1);
        v_iso1 = edv * ones(1,15);
        p_iso1 = linspace(edp, aop, 15);
        v_ej = linspace(edv, esv, 30);
        p_ej = linspace(aop, esp, 30) + sin(linspace(0,pi,30)) .* (plvp-aop)*0.4;
        v_iso2 = esv * ones(1,15);
        p_iso2 = linspace(esp, max(0, A_EDP*(exp(bedp*(esv-V0))-1)), 15);
        plot([v_fill v_iso1 v_ej v_iso2], [p_fill p_iso1 p_ej p_iso2], ...
             'Color', [colors3(c+1,:) 0.5], 'LineWidth', 0.8);
    end
end
% ESPVR 참고선
ees_ref = [2.5, 1.5, 0.8];
v_line = linspace(V0, 120, 50);
for c = 0:2
    plot(v_line, ees_ref(c+1) .* (v_line - V0), '--', ...
         'Color', colors3(c+1,:), 'LineWidth', 1.5);
end
xlabel('Volume (mL)'); ylabel('Pressure (mmHg)');
title('역추정 PV Loops (실제 데이터)', 'FontWeight', 'bold');
xlim([0 250]); ylim([0 250]);
legend(hf_names, 'Location', 'northwest', 'FontSize', 7); hold off;

% 6-2: Frank-Starling Curves
subplot(4,3,2); hold on;
edv_range = linspace(60, 250, 100);
for c = 0:2
    ees_v = ees_ref(c+1);
    sv_v = max(edv_range - max(V0+1, min(edv_range-2, V0 + 100/ees_v)), 0);
    plot(edv_range, sv_v, 'Color', colors3(c+1,:), 'LineWidth', 2.5);
end
% 실제 데이터 포인트
for c = 0:2
    idx = T.HF_class == c;
    scatter(T.EDV_est(idx), T.SV_est(idx), 20, colors3(c+1,:), 'filled', ...
            'MarkerFaceAlpha', 0.4);
end
xlabel('EDV (mL)'); ylabel('SV (mL)');
title('Frank-Starling + 실제 데이터', 'FontWeight', 'bold');
legend([hf_names, strcat(hf_names, ' (데이터)')], 'FontSize', 6); hold off;

% 6-3: EF 분포 (사망/생존)
subplot(4,3,3); hold on;
histogram(T.ejection_fraction(T.DEATH_EVENT==0), 10:5:85, ...
    'FaceColor', colors2(1,:), 'FaceAlpha', 0.6, 'EdgeColor', 'w');
histogram(T.ejection_fraction(T.DEATH_EVENT==1), 10:5:85, ...
    'FaceColor', colors2(2,:), 'FaceAlpha', 0.6, 'EdgeColor', 'w');
xline(40, 'r--', 'HFrEF cutoff', 'LineWidth', 1.5);
xline(50, 'Color', [1 0.6 0], 'LineStyle', '--', 'Label', 'HFmrEF cutoff', 'LineWidth', 1);
xlabel('Ejection Fraction (%)'); ylabel('Count');
title('EF 분포 (실제 데이터)', 'FontWeight', 'bold');
legend('생존', '사망', 'FontSize', 8); hold off;

% 6-4: Ees 분포 by HF class
subplot(4,3,4); hold on;
for c = 0:2
    histogram(Ees_est(hf_class==c), linspace(0.3, 4, 25), ...
        'FaceColor', colors3(c+1,:), 'FaceAlpha', 0.6, 'EdgeColor', 'w');
end
xlabel('역추정 Ees (mmHg/mL)'); ylabel('Count');
title('Ees 분포 (역추정)', 'FontWeight', 'bold');
legend(hf_names); hold off;

% 6-5: ROC Curve (사망 예측)
subplot(4,3,5);
plot(fpr_d, tpr_d, 'Color', colors2(2,:), 'LineWidth', 2.5); hold on;
plot([0 1], [0 1], 'k--', 'LineWidth', 0.5);
xlabel('False Positive Rate'); ylabel('True Positive Rate');
title(sprintf('ROC — 사망 예측 (AUC=%.3f)', auc_death), 'FontWeight', 'bold');
text(0.5, 0.3, sprintf('Sensitivity: %.2f\nSpecificity: %.2f\n5-Fold CV AUC: %.3f±%.3f', ...
    sensitivity, specificity, mean(cv_aucs), std(cv_aucs)), 'FontSize', 8, ...
    'BackgroundColor', [1 1 1 0.8]); hold off;

% 6-6: Feature Importance (Top 12)
subplot(4,3,6);
top_k = min(12, length(imp_sorted));
barh(1:top_k, imp_sorted(1:top_k), 'FaceColor', [74/255 123/255 255/255]);
set(gca, 'YTick', 1:top_k, 'YTickLabel', feature_names(imp_idx(1:top_k)));
set(gca, 'YDir', 'reverse');
xlabel('Permutation Importance');
title('Feature Importance — 사망 예측', 'FontWeight', 'bold');

% 6-7: Confusion Matrix (사망 예측)
subplot(4,3,7);
cm_d = confusionmat(y_test_d, pred_d);
confusionchart(cm_d, {'생존', '사망'}, ...
    'Title', sprintf('Confusion Matrix (Acc=%.3f)', acc_death));

% 6-8: Ees vs EF (실제 데이터 기반)
subplot(4,3,8); hold on;
for c = 0:2
    idx = T.HF_class == c;
    scatter(T.Ees_est(idx), T.ejection_fraction(idx), 25, colors3(c+1,:), ...
            'filled', 'MarkerFaceAlpha', 0.6);
end
xlabel('역추정 Ees (mmHg/mL)'); ylabel('EF (%)');
title('Ees vs EF (실제 환자)', 'FontWeight', 'bold');
yline(40, 'r--', 'HFrEF'); yline(50, '--', 'Color', [1 0.6 0]);
legend(hf_names, 'FontSize', 7); hold off;

% 6-9: Ees 회귀 (True vs Predicted)
subplot(4,3,9); hold on;
for c = 0:2
    mask = y_test_h == c;
    scatter(y_test_e(mask), pred_e(mask), 25, colors3(c+1,:), ...
            'filled', 'MarkerFaceAlpha', 0.6);
end
plot([0 4], [0 4], 'k--', 'LineWidth', 0.5);
xlabel('True Ees (역추정)'); ylabel('Predicted Ees');
title(sprintf('Ees 회귀 (R²=%.3f, MAE=%.3f)', r2_ees, mae_ees), 'FontWeight', 'bold');
legend(hf_names, 'FontSize', 7); hold off;

% 6-10: Serum Creatinine by Outcome
subplot(4,3,10);
bp_data = {T.serum_creatinine(T.DEATH_EVENT==0), T.serum_creatinine(T.DEATH_EVENT==1)};
max_len = max(cellfun(@length, bp_data));
bp_mat = NaN(max_len, 2);
bp_mat(1:length(bp_data{1}), 1) = bp_data{1};
bp_mat(1:length(bp_data{2}), 2) = bp_data{2};
boxplot(bp_mat, 'Labels', {'생존', '사망'}, 'Colors', colors2);
ylabel('Serum Creatinine (mg/dL)');
title('Creatinine by 예후', 'FontWeight', 'bold');

% 6-11: 연령 vs Ees (사망 색상)
subplot(4,3,11); hold on;
idx0 = T.DEATH_EVENT == 0; idx1 = T.DEATH_EVENT == 1;
scatter(T.age(idx0), T.Ees_est(idx0), 20, colors2(1,:), 'filled', 'MarkerFaceAlpha', 0.4);
scatter(T.age(idx1), T.Ees_est(idx1), 30, colors2(2,:), 'filled', 'MarkerFaceAlpha', 0.7);
xlabel('Age'); ylabel('Ees (mmHg/mL)');
title('연령 vs Ees (예후별)', 'FontWeight', 'bold');
legend('생존', '사망', 'FontSize', 8); hold off;

% 6-12: 모델 아키텍처 다이어그램
subplot(4,3,12); axis off;
arch_text = {
    '┌─────────────────────────────────────┐'
    '│   PINN-Inspired Architecture        │'
    '├─────────────────────────────────────┤'
    '│                                     │'
    '│  REAL DATA (UCI HF, N=299)          │'
    '│    age, EF, creatinine, sodium...   │'
    '│              ↓                      │'
    '│  PHYSICS-INFORMED TRANSFORM         │'
    '│    EF → Ees, EDV, ESV, SV, EDP     │'
    '│    (ESPVR: P=Ees×(V-V0))           │'
    '│    (EDPVR: P=A×(e^(B(V-V0))-1))   │'
    '│              ↓                      │'
    '│  FEATURE VECTOR (22 features)       │'
    '│    Clinical(10) + PV(8) + Derived(4)│'
    '│              ↓                      │'
    '│  ┌───────────────────────┐          │'
    '│  │ TreeBagger (200 trees)│→ Death?  │'
    '│  │ LSBoost Ensemble      │→ Ees est │'
    '│  └───────────────────────┘          │'
    '│                                     │'
    '│  Ref: Suga 1974, Burkhoff 2005     │'
    '│       Chicco & Jurman, BMC MI 2020  │'
    '│       arxiv:2401.07331 (PINN)       │'
    '└─────────────────────────────────────┘'
};
text(0.02, 0.98, arch_text, 'FontName', 'FixedWidth', 'FontSize', 7.5, ...
     'VerticalAlignment', 'top', 'BackgroundColor', [0.94 0.96 1.0], ...
     'EdgeColor', [74/255 123/255 255/255], 'Margin', 6);

% 저장
saveas(fig, 'PINN_PVloop_RealData_results.png');
fprintf('\n  [저장] PINN_PVloop_RealData_results.png\n');

%% =====================================================================
%  STEP 7: 요약 & CSV 저장
%  =====================================================================
fprintf('\n=== STEP 7: 최종 요약 ===\n');

writetable(T, 'UCI_HF_with_PV_features.csv');
fprintf('  [저장] UCI_HF_with_PV_features.csv (원본+PV역추정 변수 포함)\n');

fprintf('\n╔═══════════════════════════════════════════════════════════════╗\n');
fprintf('║     PINN 기반 PV 루프 심기능 평가 — 최종 결과 요약          ║\n');
fprintf('╠═══════════════════════════════════════════════════════════════╣\n');
fprintf('║                                                               ║\n');
fprintf('║  데이터: UCI Heart Failure Clinical Records                   ║\n');
fprintf('║    출처: Chicco & Jurman, BMC Med Inform Decis Mak, 2020     ║\n');
fprintf('║    표본: %d명 (사망 %d명 / 생존 %d명)                       ║\n', ...
    N, sum(T.DEATH_EVENT), sum(T.DEATH_EVENT==0));
fprintf('║    라이선스: CC BY 4.0                                        ║\n');
fprintf('║                                                               ║\n');
fprintf('║  Physics-Informed 특징 추출:                                  ║\n');
fprintf('║    EF → ESPVR/EDPVR 역모델 → Ees, EDV, ESV, SV, EDP, CO    ║\n');
fprintf('║    총 22개 특징 (임상 10 + PV역추정 8 + 파생 4)              ║\n');
fprintf('║                                                               ║\n');
fprintf('║  Task A: 사망 예측 (Random Forest)                           ║\n');
fprintf('║    Test Accuracy: %.3f                                       ║\n', acc_death);
fprintf('║    Test AUC: %.3f                                            ║\n', auc_death);
fprintf('║    5-Fold CV AUC: %.3f ± %.3f                               ║\n', mean(cv_aucs), std(cv_aucs));
fprintf('║    Sensitivity: %.3f, Specificity: %.3f                      ║\n', sensitivity, specificity);
fprintf('║                                                               ║\n');
fprintf('║  Task B: HF 등급 분류 — Accuracy: %.3f                      ║\n', acc_hf);
fprintf('║  Task C: Ees 회귀 — R²=%.3f, MAE=%.4f                      ║\n', r2_ees, mae_ees);
fprintf('║                                                               ║\n');
fprintf('║  Top 3 Features (사망 예측):                                  ║\n');
fprintf('║    1. %-20s (%.4f)                                ║\n', feature_names{imp_idx(1)}, imp_sorted(1));
fprintf('║    2. %-20s (%.4f)                                ║\n', feature_names{imp_idx(2)}, imp_sorted(2));
fprintf('║    3. %-20s (%.4f)                                ║\n', feature_names{imp_idx(3)}, imp_sorted(3));
fprintf('╚═══════════════════════════════════════════════════════════════╝\n');
fprintf('\n완료!\n');
