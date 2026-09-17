// Orbit camera + click picking.  Deliberately mouse-only and stateless: a student should be able to use it
// without being told anything (drag = turn, wheel = zoom, middle drag = pan, click = identify).
#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Pawn.h"
#include "HeartPawn.generated.h"

class AHeartAssembly;
class UCameraComponent;
class USpringArmComponent;

UCLASS()
class HEARTTEACH_API AHeartPawn : public APawn
{
	GENERATED_BODY()

public:
	AHeartPawn();

	UPROPERTY(EditAnywhere, Category = "Heart") TObjectPtr<AHeartAssembly> Heart;
	UPROPERTY(EditAnywhere, Category = "Heart") float OrbitSpeed = 0.35f;
	UPROPERTY(EditAnywhere, Category = "Heart") float ZoomStep = 0.12f;
	UPROPERTY(EditAnywhere, Category = "Heart") float MinArm = 40.f;
	UPROPERTY(EditAnywhere, Category = "Heart") float MaxArm = 400.f;
	/** Pitch limits: the heart has an up, and letting the camera roll past vertical only disorients people. */
	UPROPERTY(EditAnywhere, Category = "Heart") float MinPitch = -80.f;
	UPROPERTY(EditAnywhere, Category = "Heart") float MaxPitch = 80.f;

	/** Frames the heart the way the pipeline renders it: anterior towards the camera, apex down,
	 *  the patient's left on the viewer's right.  Mirrors the figures in PIPELINE.md / EDUCATION_PACK.md. */
	UFUNCTION(BlueprintCallable, Category = "Heart") void ResetView();

protected:
	virtual void SetupPlayerInputComponent(class UInputComponent* PlayerInputComponent) override;
	virtual void BeginPlay() override;
	virtual void Tick(float DeltaSeconds) override;

private:
	void OnDragPressed();
	void OnDragReleased();
	void OnPanPressed();
	void OnPanReleased();
	void OnZoom(float Value);
	void OnClick();

	UPROPERTY(Transient) TObjectPtr<USpringArmComponent> Arm;
	UPROPERTY(Transient) TObjectPtr<UCameraComponent> Camera;

	bool bOrbiting = false;
	bool bPanning = false;
	FVector2D LastMouse = FVector2D::ZeroVector;
};
