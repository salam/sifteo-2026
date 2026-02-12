using System;

namespace Sifteo;

public struct Color
{
	private readonly byte mData;

	public static Color Black => new Color(0, 0, 0);

	public static Color White => new Color(255, 255, 255);

	public static Color Mask => new Color(72, 255, 170);

	public byte Data => mData;

	public Color(int r, int g, int b)
	{
		mData = RgbData(r, g, b);
	}

	public Color(int c)
	{
		mData = Convert.ToByte(c);
	}

	public static byte RgbData(int r, int g, int b)
	{
		return (byte)(Convert.ToByte((int)Math.Round((double)(r * 7) / 255.0) << 5) | Convert.ToByte((int)Math.Round((double)(g * 7) / 255.0) << 2) | Convert.ToByte(Math.Round((double)(b * 3) / 255.0)));
	}
}
