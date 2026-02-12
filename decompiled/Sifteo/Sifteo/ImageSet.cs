using System.Collections;
using System.Collections.Generic;

namespace Sifteo;

public class ImageSet : IEnumerable
{
	private Dictionary<string, ImageInfo> imageInfos = new Dictionary<string, ImageInfo>();

	public ImageInfo this[string name] => InfoFor(name);

	internal ImageSet()
	{
	}

	internal void Add(ImageInfo i)
	{
		if (!imageInfos.ContainsKey(i.name))
		{
			imageInfos.Add(i.name, i);
		}
	}

	IEnumerator IEnumerable.GetEnumerator()
	{
		return imageInfos.Values.GetEnumerator();
	}

	public bool Contains(string name)
	{
		return imageInfos.ContainsKey(name);
	}

	public ImageInfo InfoFor(string name)
	{
		if (!imageInfos.ContainsKey(name))
		{
			throw new KeyNotFoundException($"ImageSet: does not contain {name}");
		}
		return imageInfos[name];
	}
}
