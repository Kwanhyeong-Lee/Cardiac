// Row types for the DataTables that 01_import_assets.py writes from fusion_ready/UNREAL/<case>/unreal_manifest.json.
// Everything the app knows about the heart comes from those tables, so a new case is a re-import, not a code change.
#pragma once

#include "CoreMinimal.h"
#include "Engine/DataTable.h"
#include "HeartData.generated.h"

/** Provenance of a part -- shown next to whatever the student is looking at.  The model mixes three very
 *  different kinds of geometry and the teaching value depends on never blurring them. */
UENUM(BlueprintType)
enum class EHeartProvenance : uint8
{
	Patient     UMETA(DisplayName = "환자 CT 그대로"),
	Parametric  UMETA(DisplayName = "파라메트릭 (문헌 비율)"),
	Synthetic   UMETA(DisplayName = "합성 (두께 가정)")
};

USTRUCT(BlueprintType)
struct FHeartPartRow : public FTableRowBase
{
	GENERATED_BODY()

	/** Matches the mesh asset name and the key used everywhere else (RV_wall, LV_myocardium, ...). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly) FName PartName;
	UPROPERTY(EditAnywhere, BlueprintReadOnly) TSoftObjectPtr<UStaticMesh> Mesh;
	UPROPERTY(EditAnywhere, BlueprintReadOnly) FLinearColor Colour = FLinearColor::White;
	UPROPERTY(EditAnywhere, BlueprintReadOnly) EHeartProvenance Provenance = EHeartProvenance::Patient;
	/** The exact sentence from the pipeline manifest -- do not paraphrase it in the UI. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly) FText ProvenanceNote;
	UPROPERTY(EditAnywhere, BlueprintReadOnly) float VolumeML = 0.f;
	/** LV_myocardium carries three colours of its own (myocardium / septum / papillary); do not tint it. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly) bool bUseVertexColours = false;
	UPROPERTY(EditAnywhere, BlueprintReadOnly) FText DisplayName;
};

/** One occlusion scenario from step 20 (ct_perfusion_territories.py). */
USTRUCT(BlueprintType)
struct FHeartTerritoryRow : public FTableRowBase
{
	GENERATED_BODY()

	UPROPERTY(EditAnywhere, BlueprintReadOnly) FText Site;
	/** LM / LAD / LCx / RCA -- which vessel the student clicked. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly) FName Vessel;
	UPROPERTY(EditAnywhere, BlueprintReadOnly) float MassAtRiskG = 0.f;
	UPROPERTY(EditAnywhere, BlueprintReadOnly) float PercentOfLV = 0.f;
};

/** One of the (at most six) exact vertex colours of the territory mesh.  Territory AND confidence are both
 *  encoded in the colour, so the material selects a territory by comparing vertex colour -- no second mesh,
 *  no per-vertex attribute.  VertexCount == 0 means this combination does not occur in this patient
 *  (1009: no LAD voxel is prior-assigned, every one of them is measured). */
USTRUCT(BlueprintType)
struct FHeartTerritoryColourRow : public FTableRowBase
{
	GENERATED_BODY()

	UPROPERTY(EditAnywhere, BlueprintReadOnly) FName Vessel;
	UPROPERTY(EditAnywhere, BlueprintReadOnly) bool bMeasured = true;
	UPROPERTY(EditAnywhere, BlueprintReadOnly) FLinearColor Colour = FLinearColor::White;
	UPROPERTY(EditAnywhere, BlueprintReadOnly) int32 VertexCount = 0;
};
