using UnrealBuildTool;
using System.Collections.Generic;

public class HeartTeachTarget : TargetRules
{
	public HeartTeachTarget(TargetInfo Target) : base(Target)
	{
		Type = TargetType.Game;
		DefaultBuildSettings = BuildSettingsVersion.Latest;
		IncludeOrderVersion = EngineIncludeOrderVersion.Latest;
		ExtraModuleNames.Add("HeartTeach");
	}
}
