using System.Collections.Generic;

namespace Sifteo.Util;

public class CubeHelper
{
	private static List<Cube> ScratchPad = new List<Cube>(6);

	private static readonly Cube.Side[,] kLookupTable = new Cube.Side[4, 4]
	{
		{
			Cube.Side.BOTTOM,
			Cube.Side.RIGHT,
			Cube.Side.TOP,
			Cube.Side.LEFT
		},
		{
			Cube.Side.LEFT,
			Cube.Side.BOTTOM,
			Cube.Side.RIGHT,
			Cube.Side.TOP
		},
		{
			Cube.Side.TOP,
			Cube.Side.LEFT,
			Cube.Side.BOTTOM,
			Cube.Side.RIGHT
		},
		{
			Cube.Side.RIGHT,
			Cube.Side.TOP,
			Cube.Side.LEFT,
			Cube.Side.BOTTOM
		}
	};

	public static Cube[] FindColumn(CubeSet cubes)
	{
		foreach (Cube cube2 in cubes)
		{
			if (cube2.Neighbors.Top != null && cube2.Neighbors.Left == null && cube2.Neighbors.Right == null && cube2.Neighbors.Bottom == null)
			{
				ScratchPad.Add(cube2);
				Cube cube = cube2;
				while (cube.Neighbors.Top != null && cube.Neighbors.Top.Neighbors.Bottom == cube)
				{
					cube = cube.Neighbors.Top;
					ScratchPad.Add(cube);
				}
				break;
			}
		}
		Cube[] result = ScratchPad.ToArray();
		ScratchPad.Clear();
		return result;
	}

	public static Cube[] FindRow(CubeSet cubes)
	{
		foreach (Cube cube2 in cubes)
		{
			if (cube2.Neighbors.Right != null && cube2.Neighbors.Left == null && cube2.Neighbors.Top == null && cube2.Neighbors.Bottom == null)
			{
				ScratchPad.Add(cube2);
				Cube cube = cube2;
				while (cube.Neighbors.Right != null && cube.Neighbors.Right.Neighbors.Left == cube)
				{
					cube = cube.Neighbors.Right;
					ScratchPad.Add(cube);
				}
				break;
			}
		}
		Cube[] result = ScratchPad.ToArray();
		ScratchPad.Clear();
		return result;
	}

	public static Cube[] FindConnected(Cube cube)
	{
		Visit(cube);
		Cube[] result = ScratchPad.ToArray();
		ScratchPad.Clear();
		return result;
	}

	public static Cube.Side RotateFromOriginToNeighbor(Cube.Side originDir, Cube origin, Cube destination)
	{
		Cube.Side side = origin.Neighbors.SideOf(destination);
		Cube.Side side2 = destination.Neighbors.SideOf(origin);
		if (originDir == Cube.Side.NONE || side == Cube.Side.NONE || side2 == Cube.Side.NONE)
		{
			return originDir;
		}
		return (Cube.Side)(((int)originDir + (int)kLookupTable[(int)side, (int)side2]) % 4);
	}

	public static Cube.Side RotateSideClockwise(Cube.Side side)
	{
		if (side == Cube.Side.NONE)
		{
			return Cube.Side.NONE;
		}
		return (Cube.Side)((int)(side + 3) % 4);
	}

	public static Cube.Side InvertSide(Cube.Side side)
	{
		if (side == Cube.Side.NONE)
		{
			return Cube.Side.NONE;
		}
		return (Cube.Side)((int)(side + 2) % 4);
	}

	public static Cube.Side RotateSideAnticlockwise(Cube.Side side)
	{
		if (side == Cube.Side.NONE)
		{
			return Cube.Side.NONE;
		}
		return (Cube.Side)((int)(side + 1) % 4);
	}

	private static void Visit(Cube cube)
	{
		if (cube != null && !ScratchPad.Contains(cube))
		{
			ScratchPad.Add(cube);
			Visit(cube.Neighbors.Top);
			Visit(cube.Neighbors.Bottom);
			Visit(cube.Neighbors.Left);
			Visit(cube.Neighbors.Right);
		}
	}
}
