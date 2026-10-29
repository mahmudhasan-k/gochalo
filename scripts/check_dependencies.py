"""Check installed runtime/development requirements without requiring pip."""
from importlib import metadata
from packaging.requirements import Requirement
issues=[]
for distribution in metadata.distributions():
    for text in distribution.requires or []:
        requirement=Requirement(text)
        if requirement.marker and not requirement.marker.evaluate({"extra":""}):
            continue
        try:
            version=metadata.version(requirement.name)
        except metadata.PackageNotFoundError:
            issues.append(f"{distribution.metadata['Name']}: missing {requirement.name}")
            continue
        if requirement.specifier and not requirement.specifier.contains(version,prereleases=True):
            issues.append(f"{distribution.metadata['Name']}: incompatible {requirement.name} {version}")
if issues:
    raise SystemExit("\n".join(issues))
print("No broken installed requirements found.")
