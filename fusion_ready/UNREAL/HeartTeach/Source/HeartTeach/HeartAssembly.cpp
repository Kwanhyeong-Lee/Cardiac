#include "HeartAssembly.h"

#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Kismet/KismetMaterialLibrary.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Materials/MaterialParameterCollection.h"

// Parameter names must match the ones 02_build_materials.py creates.
static const FName P_ClipOrigin(TEXT("ClipOrigin"));
static const FName P_ClipNormal(TEXT("ClipNormal"));
static const FName P_ClipEnabled(TEXT("ClipEnabled"));
static const FName P_Tint(TEXT("Tint"));
static const FName P_UseVertexColour(TEXT("UseVertexColour"));
static const FName P_Opacity(TEXT("Opacity"));
static const FName P_Highlight(TEXT("Highlight"));
static const FName P_DeadColour(TEXT("DeadColour"));   // the greyed-out territory colour (RGB) + A = enabled
static const FName P_DeadMatchA(TEXT("DeadMatchA"));   // measured colour of the occluded vessel
static const FName P_DeadMatchB(TEXT("DeadMatchB"));   // prior-assigned (pale) colour of the same vessel

AHeartAssembly::AHeartAssembly()
{
	PrimaryActorTick.bCanEverTick = false;
	Root = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
	SetRootComponent(Root);
}

void AHeartAssembly::OnConstruction(const FTransform& Transform)
{
	Super::OnConstruction(Transform);
	Rebuild();
}

void AHeartAssembly::BeginPlay()
{
	Super::BeginPlay();
	if (Parts.Num() == 0) { Rebuild(); }
	SetClipEnabled(false);
}

void AHeartAssembly::Rebuild()
{
	for (auto& It : Parts) { if (It.Value) { It.Value->DestroyComponent(); } }
	Parts.Reset(); Materials.Reset(); ExplodeDirections.Reset();
	if (!PartsTable) { return; }

	Root->SetWorldScale3D(FVector(DisplayScale));

	TArray<FHeartPartRow*> Rows;
	PartsTable->GetAllRows<FHeartPartRow>(TEXT("AHeartAssembly::Rebuild"), Rows);

	FBox Bounds(ForceInit);
	for (const FHeartPartRow* Row : Rows)
	{
		if (!Row || Row->PartName.IsNone()) { continue; }
		UStaticMesh* Mesh = Row->Mesh.LoadSynchronous();
		if (!Mesh) { UE_LOG(LogTemp, Warning, TEXT("HeartAssembly: mesh missing for %s"), *Row->PartName.ToString()); continue; }

		UStaticMeshComponent* Comp = NewObject<UStaticMeshComponent>(this, Row->PartName);
		Comp->SetupAttachment(Root);
		Comp->SetStaticMesh(Mesh);
		Comp->SetCollisionEnabled(ECollisionEnabled::QueryOnly);      // clicks only; nothing here simulates
		Comp->SetCollisionResponseToAllChannels(ECR_Block);
		Comp->RegisterComponent();

		if (PartMaterial)
		{
			UMaterialInstanceDynamic* MID = UMaterialInstanceDynamic::Create(PartMaterial, this);
			MID->SetVectorParameterValue(P_Tint, Row->Colour);
			MID->SetScalarParameterValue(P_UseVertexColour, Row->bUseVertexColours ? 1.f : 0.f);
			MID->SetScalarParameterValue(P_Opacity, 1.f);
			MID->SetScalarParameterValue(P_Highlight, 0.f);
			Comp->SetMaterial(0, MID);
			Materials.Add(Row->PartName, MID);
		}

		Parts.Add(Row->PartName, Comp);
		if (Row->PartName == FName(TEXT("LV_myocardium"))) { LVOriginalMesh = Mesh; }
		Bounds += Mesh->GetBoundingBox();
	}

	// explode direction = each part's own centre relative to the whole, so parts move apart instead of scattering
	const FVector Centre = Bounds.GetCenter();
	for (const auto& It : Parts)
	{
		const FVector D = It.Value->GetStaticMesh()->GetBoundingBox().GetCenter() - Centre;
		ExplodeDirections.Add(It.Key, D.GetSafeNormal() * FMath::Max(D.Size(), 1.f));
	}
}

UMaterialInstanceDynamic* AHeartAssembly::MaterialFor(FName PartName) const
{
	const TObjectPtr<UMaterialInstanceDynamic>* Found = Materials.Find(PartName);
	return Found ? Found->Get() : nullptr;
}

bool AHeartAssembly::GetPart(FName PartName, FHeartPartRow& OutRow) const
{
	if (!PartsTable) { return false; }
	if (const FHeartPartRow* Row = PartsTable->FindRow<FHeartPartRow>(PartName, TEXT("GetPart"), false))
	{
		OutRow = *Row; return true;
	}
	return false;
}

TArray<FName> AHeartAssembly::GetPartNames() const
{
	TArray<FName> Names; Parts.GetKeys(Names); return Names;
}

void AHeartAssembly::SetPartVisible(FName PartName, bool bVisible)
{
	if (TObjectPtr<UStaticMeshComponent>* Comp = Parts.Find(PartName)) { (*Comp)->SetVisibility(bVisible); }
}

void AHeartAssembly::SetPartOpacity(FName PartName, float Opacity)
{
	if (UMaterialInstanceDynamic* MID = MaterialFor(PartName)) { MID->SetScalarParameterValue(P_Opacity, FMath::Clamp(Opacity, 0.f, 1.f)); }
}

void AHeartAssembly::IsolatePart(FName PartName)
{
	for (const auto& It : Parts)
	{
		const bool bIsTarget = (PartName.IsNone() || It.Key == PartName);
		SetPartOpacity(It.Key, bIsTarget ? 1.f : 0.12f);
	}
}

void AHeartAssembly::ShowAll()
{
	for (const auto& It : Parts) { It.Value->SetVisibility(true); SetPartOpacity(It.Key, 1.f); HighlightPart(It.Key, false); }
	SetExplode(0.f);
}

void AHeartAssembly::SetExplode(float Alpha)
{
	for (const auto& It : Parts)
	{
		const FVector* D = ExplodeDirections.Find(It.Key);
		It.Value->SetRelativeLocation(D ? (*D) * Alpha : FVector::ZeroVector);
	}
}

void AHeartAssembly::HighlightPart(FName PartName, bool bOn)
{
	if (UMaterialInstanceDynamic* MID = MaterialFor(PartName)) { MID->SetScalarParameterValue(P_Highlight, bOn ? 1.f : 0.f); }
}

// ---------------------------------------------------------------- clip plane

void AHeartAssembly::SetClipEnabled(bool bEnabled)
{
	if (!ClipCollection) { return; }
	UKismetMaterialLibrary::SetScalarParameterValue(this, ClipCollection, P_ClipEnabled, bEnabled ? 1.f : 0.f);
	if (bEnabled) { SetClipPlane(DefaultClipOrigin, DefaultClipNormal); }
}

void AHeartAssembly::SetClipPlane(FVector Origin, FVector Normal)
{
	if (!ClipCollection) { return; }
	const FVector N = Normal.GetSafeNormal();
	UKismetMaterialLibrary::SetVectorParameterValue(this, ClipCollection, P_ClipOrigin, FLinearColor(Origin));
	UKismetMaterialLibrary::SetVectorParameterValue(this, ClipCollection, P_ClipNormal, FLinearColor(N));
}

void AHeartAssembly::SetClipOffset(float Centimetres)
{
	SetClipPlane(DefaultClipOrigin + DefaultClipNormal * Centimetres, DefaultClipNormal);
}

// ---------------------------------------------------------------- perfusion

FName AHeartAssembly::VesselOfPart(FName PartName)
{
	const FString S = PartName.ToString();
	if (!S.StartsWith(TEXT("coronary_"))) { return NAME_None; }
	FString Mid = S.RightChop(9);                                     // coronary_LAD_system -> LAD_system
	Mid.RemoveFromEnd(TEXT("_system"));
	return FName(*Mid);
}

void AHeartAssembly::SetPerfusionMode(bool bOn)
{
	bPerfusionMode = bOn;
	TObjectPtr<UStaticMeshComponent>* LV = Parts.Find(FName(TEXT("LV_myocardium")));
	if (!LV || !*LV) { return; }
	UStaticMesh* Target = bOn ? TerritoryMesh.Get() : LVOriginalMesh.Get();
	if (Target) { (*LV)->SetStaticMesh(Target); }
	if (UMaterialInstanceDynamic* MID = MaterialFor(FName(TEXT("LV_myocardium"))))
	{
		MID->SetScalarParameterValue(P_UseVertexColour, 1.f);         // both meshes carry their own vertex colours
	}
	if (!bOn) { ClearOcclusion(); }
}

float AHeartAssembly::OccludeVessel(FName Vessel)
{
	UMaterialInstanceDynamic* MID = MaterialFor(FName(TEXT("LV_myocardium")));
	if (!MID || !TerritoryColourTable) { return -1.f; }

	// the two exact vertex colours of this vessel: measured, and assigned-by-prior (pale)
	FLinearColor Measured = FLinearColor::Black, Prior = FLinearColor::Black;
	TArray<FHeartTerritoryColourRow*> Colours;
	TerritoryColourTable->GetAllRows<FHeartTerritoryColourRow>(TEXT("OccludeVessel"), Colours);
	for (const FHeartTerritoryColourRow* C : Colours)
	{
		if (!C || C->Vessel != Vessel) { continue; }
		(C->bMeasured ? Measured : Prior) = C->Colour;
	}
	MID->SetVectorParameterValue(P_DeadMatchA, Measured);
	MID->SetVectorParameterValue(P_DeadMatchB, Prior);
	MID->SetVectorParameterValue(P_DeadColour, FLinearColor(0.35f, 0.35f, 0.35f, 1.f));

	if (!TerritoryTable) { return -1.f; }
	float Best = -1.f;                                                // the proximal (largest) scenario for that vessel
	TArray<FHeartTerritoryRow*> Rows;
	TerritoryTable->GetAllRows<FHeartTerritoryRow>(TEXT("OccludeVessel"), Rows);
	for (const FHeartTerritoryRow* R : Rows)
	{
		if (R && R->Vessel == Vessel) { Best = FMath::Max(Best, R->MassAtRiskG); }
	}
	return Best;
}

void AHeartAssembly::ClearOcclusion()
{
	if (UMaterialInstanceDynamic* MID = MaterialFor(FName(TEXT("LV_myocardium"))))
	{
		MID->SetVectorParameterValue(P_DeadColour, FLinearColor(0.f, 0.f, 0.f, 0.f));   // A = 0 disables the swap
	}
}

void AHeartAssembly::NotifyClicked(UPrimitiveComponent* Component)
{
	if (!Component) { return; }
	for (const auto& It : Parts)
	{
		if (It.Value == Component) { OnPartClicked.Broadcast(It.Key); return; }
	}
}
