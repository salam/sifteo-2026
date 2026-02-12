namespace Sifteo.MathExt;

public struct Matrix
{
	public static Matrix Identity = new Matrix(1f, 0f, 0f, 1f, 0f, 0f);

	public Float2 u;

	public Float2 v;

	public Float2 t;

	public Matrix Inverse
	{
		get
		{
			float magnitude = u.Magnitude;
			float magnitude2 = v.Magnitude;
			return new Matrix(u.Conjugate / (magnitude * magnitude), v.Conjugate / (magnitude2 * magnitude2), -t);
		}
	}

	public Matrix(Float2 u, Float2 v, Float2 t)
	{
		this.u = u;
		this.v = v;
		this.t = t;
	}

	public Matrix(float ux, float uy, float vx, float vy, float tx, float ty)
	{
		u.x = ux;
		u.y = uy;
		v.x = vx;
		v.y = vy;
		t.x = tx;
		t.y = ty;
	}

	public static Matrix Translation(Float2 v)
	{
		return Translation(v.x, v.y);
	}

	public static Matrix Translation(float x, float y)
	{
		return new Matrix(1f, 0f, 0f, 1f, x, y);
	}

	public static Matrix Scale(float x, float y)
	{
		return new Matrix(x, 0f, 0f, y, 0f, 0f);
	}

	public static Matrix Scale(Float2 v)
	{
		return new Matrix(v.x, 0f, 0f, v.y, 0f, 0f);
	}

	public static Matrix Rotation(float radians)
	{
		float num = Mathf.Cos(radians);
		float num2 = Mathf.Sin(radians);
		return new Matrix(num, num2, 0f - num2, num, 0f, 0f);
	}

	public static Matrix Rotation(Float2 unit)
	{
		return Rotation(unit.Radians);
	}

	public static Matrix TRS(Float2 translation, Float2 orientation, Float2 scale)
	{
		return new Matrix(orientation.x * scale.x, orientation.y * scale.x, (0f - orientation.y) * scale.y, orientation.x * scale.y, translation.x, translation.y);
	}

	public Float2 TransformPoint(Float2 p)
	{
		return new Float2(u.x * p.x + v.x * p.y + t.x, u.y * p.x + v.y * p.y + t.y);
	}

	public Float2 TransformDirection(Float2 p)
	{
		return new Float2(u.x * p.x + v.x * p.y, u.y * p.x + v.y * p.y);
	}

	public Float2 InverseTransformPoint(Float2 p)
	{
		return Inverse.TransformPoint(p);
	}

	public Float2 InverseTransformDirection(Float2 p)
	{
		return Inverse.TransformDirection(p);
	}

	public static Matrix operator *(Matrix m, Matrix n)
	{
		return new Matrix(m.u.x * n.u.x + m.v.x * n.u.y, m.u.y * n.u.x + m.v.y * n.u.y, m.u.x * n.v.x + m.v.x * n.v.y, m.u.y * n.v.x + m.v.y * n.v.y, m.u.x * n.t.x + m.v.x * n.t.y + m.t.x, m.u.y * n.t.x + m.v.y * n.t.y + m.t.y);
	}
}
