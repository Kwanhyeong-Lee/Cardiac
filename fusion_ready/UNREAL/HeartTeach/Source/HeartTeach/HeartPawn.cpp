#include "HeartPawn.h"

#include "Camera/CameraComponent.h"
#include "Components/InputComponent.h"
#include "GameFramework/PlayerController.h"
#include "GameFramework/SpringArmComponent.h"
#include "HeartAssembly.h"
#include "Kismet/GameplayStatics.h"

AHeartPawn::AHeartPawn()
{
	PrimaryActorTick.bCanEverTick = true;
	Arm = CreateDefaultSubobject<USpringArmComponent>(TEXT("Arm"));
	SetRootComponent(Arm);
	Arm->TargetArmLength = 120.f;
	Arm->bDoCollisionTest = false;                       // nothing to collide with; the model is the whole world
	Camera = CreateDefaultSubobject<UCameraComponent>(TEXT("Camera"));
	Camera->SetupAttachment(Arm);
}

void AHeartPawn::BeginPlay()
{
	Super::BeginPlay();
	if (!Heart) { Heart = Cast<AHeartAssembly>(UGameplayStatics::GetActorOfClass(GetWorld(), AHeartAssembly::StaticClass())); }
	if (APlayerController* PC = Cast<APlayerController>(GetController()))
	{
		PC->bShowMouseCursor = true;
		PC->bEnableClickEvents = true;
		PC->bEnableMouseOverEvents = true;
	}
	ResetView();
}

void AHeartPawn::ResetView()
{
	if (Heart) { SetActorLocation(Heart->GetActorLocation()); }
	// glTF import puts anterior on +Y_unreal... the pipeline frame is documented in unreal_manifest.json;
	// looking along -Y with a small downward pitch gives the anterior view used in every figure.
	SetActorRotation(FRotator(-15.f, 90.f, 0.f));
	Arm->TargetArmLength = 120.f;
}

void AHeartPawn::SetupPlayerInputComponent(UInputComponent* PlayerInputComponent)
{
	Super::SetupPlayerInputComponent(PlayerInputComponent);
	// Legacy action/axis bindings: they need no Enhanced Input assets, so the whole app stays text-only.
	// DefaultInput.ini (written by 03_build_level.py) declares Orbit / Pan / Zoom / Pick.
	PlayerInputComponent->BindAction("Orbit", IE_Pressed, this, &AHeartPawn::OnDragPressed);
	PlayerInputComponent->BindAction("Orbit", IE_Released, this, &AHeartPawn::OnDragReleased);
	PlayerInputComponent->BindAction("Pan", IE_Pressed, this, &AHeartPawn::OnPanPressed);
	PlayerInputComponent->BindAction("Pan", IE_Released, this, &AHeartPawn::OnPanReleased);
	PlayerInputComponent->BindAction("Pick", IE_Pressed, this, &AHeartPawn::OnClick);
	PlayerInputComponent->BindAxis("Zoom", this, &AHeartPawn::OnZoom);
}

void AHeartPawn::OnDragPressed()  { bOrbiting = true; }
void AHeartPawn::OnDragReleased() { bOrbiting = false; }
void AHeartPawn::OnPanPressed()   { bPanning = true; }
void AHeartPawn::OnPanReleased()  { bPanning = false; }

void AHeartPawn::OnZoom(float Value)
{
	if (FMath::IsNearlyZero(Value)) { return; }
	Arm->TargetArmLength = FMath::Clamp(Arm->TargetArmLength * (1.f - Value * ZoomStep), MinArm, MaxArm);
}

void AHeartPawn::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	APlayerController* PC = Cast<APlayerController>(GetController());
	if (!PC) { return; }

	float X = 0.f, Y = 0.f;
	PC->GetMousePosition(X, Y);
	const FVector2D Mouse(X, Y);
	const FVector2D Delta = Mouse - LastMouse;
	LastMouse = Mouse;

	if (bOrbiting)
	{
		FRotator R = GetActorRotation();
		R.Yaw   += Delta.X * OrbitSpeed;
		R.Pitch = FMath::Clamp(R.Pitch - Delta.Y * OrbitSpeed, MinPitch, MaxPitch);
		SetActorRotation(R);
	}
	else if (bPanning)
	{
		const FVector Right = GetActorRightVector(), Up = GetActorUpVector();
		const float Scale = Arm->TargetArmLength * 0.002f;
		AddActorWorldOffset((-Right * Delta.X + Up * Delta.Y) * Scale);
	}
}

void AHeartPawn::OnClick()
{
	APlayerController* PC = Cast<APlayerController>(GetController());
	if (!PC || !Heart) { return; }
	FHitResult Hit;
	if (PC->GetHitResultUnderCursor(ECC_Visibility, false, Hit) && Hit.GetComponent())
	{
		Heart->NotifyClicked(Hit.GetComponent());
	}
}
