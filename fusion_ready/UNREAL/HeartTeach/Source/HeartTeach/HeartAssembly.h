// The heart in the level: one static-mesh component per anatomical part, driven entirely by DT_HeartParts.
#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "HeartData.h"
#include "HeartAssembly.generated.h"

class UMaterialInterface;
class UMaterialInstanceDynamic;
class UMaterialParameterCollection;
class UStaticMeshComponent;

DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnHeartPartClicked, FName, PartName);

UCLASS()
class HEARTTEACH_API AHeartAssembly : public AActor
{
	GENERATED_BODY()

public:
	AHeartAssembly();

	// ---- assets (set on the CDO / in the level) ----
	UPROPERTY(EditAnywhere, Category = "Heart|Data") TObjectPtr<UDataTable> PartsTable;
	UPROPERTY(EditAnywhere, Category = "Heart|Data") TObjectPtr<UDataTable> TerritoryTable;
	UPROPERTY(EditAnywhere, Category = "Heart|Data") TObjectPtr<UDataTable> TerritoryColourTable;
	/** M_HeartPart: masked + two sided, reads MPC_HeartClip.  Built by 02_build_materials.py. */
	UPROPERTY(EditAnywhere, Category = "Heart|Data") TObjectPtr<UMaterialInterface> PartMaterial;
	UPROPERTY(EditAnywhere, Category = "Heart|Data") TObjectPtr<UMaterialParameterCollection> ClipCollection;
	/** LV myocardium coloured by perfusion territory; swapped in for LV_myocardium in perfusion mode. */
	UPROPERTY(EditAnywhere, Category = "Heart|Data") TObjectPtr<UStaticMesh> TerritoryMesh;

	/** Teaching models are looked at, not walked around: 5-10x life size reads much better on a projector. */
	UPROPERTY(EditAnywhere, Category = "Heart") float DisplayScale = 8.f;

	/** The plane the PRINTED halves are cut on, in Unreal world space (cm).  03_build_level.py converts it
	 *  from unreal_manifest.json -> four_chamber_plane, so slider zero and the physical model agree. */
	UPROPERTY(EditAnywhere, Category = "Heart|Clip") FVector DefaultClipOrigin = FVector::ZeroVector;
	UPROPERTY(EditAnywhere, Category = "Heart|Clip") FVector DefaultClipNormal = FVector::UpVector;

	UPROPERTY(BlueprintAssignable, Category = "Heart") FOnHeartPartClicked OnPartClicked;

	// ---- parts ----
	UFUNCTION(BlueprintCallable, Category = "Heart") void SetPartVisible(FName PartName, bool bVisible);
	UFUNCTION(BlueprintCallable, Category = "Heart") void SetPartOpacity(FName PartName, float Opacity);
	/** Everything except this part goes translucent; pass NAME_None to clear. */
	UFUNCTION(BlueprintCallable, Category = "Heart") void IsolatePart(FName PartName);
	UFUNCTION(BlueprintCallable, Category = "Heart") void ShowAll();
	/** 0 = assembled, 1 = parts pushed out along their own offset from the centre. */
	UFUNCTION(BlueprintCallable, Category = "Heart") void SetExplode(float Alpha);
	UFUNCTION(BlueprintCallable, Category = "Heart") void HighlightPart(FName PartName, bool bOn);
	UFUNCTION(BlueprintPure, Category = "Heart") bool GetPart(FName PartName, FHeartPartRow& OutRow) const;
	UFUNCTION(BlueprintPure, Category = "Heart") TArray<FName> GetPartNames() const;

	// ---- clip plane (world space, cm -- the same plane the printed halves are cut on) ----
	UFUNCTION(BlueprintCallable, Category = "Heart|Clip") void SetClipEnabled(bool bEnabled);
	UFUNCTION(BlueprintCallable, Category = "Heart|Clip") void SetClipPlane(FVector Origin, FVector Normal);
	/** Slides the plane along its normal; 0 = the four-chamber plane of the printed model. */
	UFUNCTION(BlueprintCallable, Category = "Heart|Clip") void SetClipOffset(float Centimetres);
	UFUNCTION(BlueprintPure, Category = "Heart|Clip") FVector GetDefaultClipOrigin() const { return DefaultClipOrigin; }
	UFUNCTION(BlueprintPure, Category = "Heart|Clip") FVector GetDefaultClipNormal() const { return DefaultClipNormal; }

	// ---- perfusion ----
	/** Swap the LV myocardium for the territory-coloured mesh. */
	UFUNCTION(BlueprintCallable, Category = "Heart|Perfusion") void SetPerfusionMode(bool bOn);
	/** Grey out the territory of this vessel ("occlude it") and return the mass at risk in grams.
	 *  Returns -1 if the table has no scenario for that vessel. */
	UFUNCTION(BlueprintCallable, Category = "Heart|Perfusion") float OccludeVessel(FName Vessel);
	UFUNCTION(BlueprintCallable, Category = "Heart|Perfusion") void ClearOcclusion();
	/** Vessel a clicked component belongs to: coronary_LAD_system -> LAD, etc.  NAME_None if not a vessel. */
	UFUNCTION(BlueprintPure, Category = "Heart|Perfusion") static FName VesselOfPart(FName PartName);

	/** Called by the player controller when a component is clicked. */
	void NotifyClicked(UPrimitiveComponent* Component);

protected:
	virtual void BeginPlay() override;
	virtual void OnConstruction(const FTransform& Transform) override;

private:
	void Rebuild();
	UMaterialInstanceDynamic* MaterialFor(FName PartName) const;

	UPROPERTY(Transient) TObjectPtr<USceneComponent> Root;
	UPROPERTY(Transient) TMap<FName, TObjectPtr<UStaticMeshComponent>> Parts;
	UPROPERTY(Transient) TMap<FName, TObjectPtr<UMaterialInstanceDynamic>> Materials;
	UPROPERTY(Transient) TMap<FName, FVector> ExplodeDirections;
	UPROPERTY(Transient) TObjectPtr<UStaticMesh> LVOriginalMesh;

	bool bPerfusionMode = false;
};
