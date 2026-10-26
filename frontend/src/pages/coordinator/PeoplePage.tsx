import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Users, UserPlus, Search, Filter, Mail, Award, BookOpen, Hash, Tag, Plus, X, Clock } from 'lucide-react';
import { apiClient, ApiError } from '@/api/client';
import { User, UserRole } from '@/types/api';
import {
  Button,
  Input,
  Select,
  FormField,
  Modal,
  Card,
  Badge,
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
  Spinner,
  EmptyState,
  useToast,
} from '@/components/ui';

export const PeoplePage: React.FC = () => {
  const queryClient = useQueryClient();
  const { success, error: toastError } = useToast();

  const [search, setSearch] = useState('');
  const [roleFilter, setRoleFilter] = useState<string>('all');
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);

  // Form state
  const [formName, setFormName] = useState('');
  const [formEmail, setFormEmail] = useState('');
  const [formPassword, setFormPassword] = useState('');
  const [formRole, setFormRole] = useState<UserRole>('interviewer');
  const [formSkills, setFormSkills] = useState<string[]>([]);
  const [skillInput, setSkillInput] = useState('');
  const [formCapacity, setFormCapacity] = useState(4);
  const [formDepartment, setFormDepartment] = useState('');
  const [formRollNumber, setFormRollNumber] = useState('');
  const [formBranch, setFormBranch] = useState('');
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

  const { data: users = [], isLoading } = useQuery<User[]>({
    queryKey: ['users', roleFilter, search],
    queryFn: () => {
      const params: Record<string, string> = {};
      if (roleFilter !== 'all') params.role = roleFilter;
      if (search.trim()) params.q = search.trim();
      return apiClient<User[]>('/users', { params });
    },
  });

  const createUserMutation = useMutation({
    mutationFn: (body: any) => apiClient<User>('/users', { method: 'POST', body: JSON.stringify(body) }),
    onSuccess: () => {
      success('User Created', 'New account and profile registered successfully');
      queryClient.invalidateQueries({ queryKey: ['users'] });
      setIsCreateModalOpen(false);
      resetForm();
    },
    onError: (err: any) => {
      if (err instanceof ApiError) {
        if (err.details && Array.isArray(err.details)) {
          const errorsMap: Record<string, string> = {};
          err.details.forEach((d: any) => {
            const field = d.loc?.[d.loc.length - 1];
            if (field) errorsMap[field] = d.msg;
          });
          setFieldErrors(errorsMap);
        } else {
          toastError('Error', err.message);
        }
      } else {
        toastError('Error', 'Failed to create user');
      }
    },
  });

  const resetForm = () => {
    setFormName('');
    setFormEmail('');
    setFormPassword('');
    setFormRole('interviewer');
    setFormSkills([]);
    setSkillInput('');
    setFormCapacity(4);
    setFormDepartment('');
    setFormRollNumber('');
    setFormBranch('');
    setFieldErrors({});
  };

  const handleAddSkill = () => {
    if (skillInput.trim() && !formSkills.includes(skillInput.trim().toLowerCase())) {
      setFormSkills([...formSkills, skillInput.trim().toLowerCase()]);
      setSkillInput('');
    }
  };

  const handleRemoveSkill = (skill: string) => {
    setFormSkills(formSkills.filter((s) => s !== skill));
  };

  const handleSubmitCreate = (e: React.FormEvent) => {
    e.preventDefault();
    setFieldErrors({});

    const payload: any = {
      name: formName,
      email: formEmail,
      password: formPassword,
      role: formRole,
    };

    if (formRole === 'interviewer') {
      payload.skills = formSkills;
      payload.capacity = Number(formCapacity);
      payload.department = formDepartment || undefined;
    } else if (formRole === 'candidate') {
      payload.roll_number = formRollNumber || undefined;
      payload.branch = formBranch || undefined;
    }

    createUserMutation.mutate(payload);
  };

  const roleBadgeVariants: Record<UserRole, 'brand' | 'success' | 'warning' | 'danger' | 'neutral'> = {
    coordinator: 'brand',
    interviewer: 'success',
    candidate: 'neutral',
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-100 tracking-tight flex items-center gap-2.5">
            <Users className="w-6 h-6 text-brand-400" />
            <span>People &amp; Directory</span>
          </h1>
          <p className="text-xs text-slate-400 mt-1">
            Manage interviewers, candidates, and coordinator staff with role-specific capacity and skill tags
          </p>
        </div>

        <Button
          variant="primary"
          size="sm"
          onClick={() => {
            resetForm();
            setIsCreateModalOpen(true);
          }}
          leftIcon={<UserPlus className="w-4 h-4" />}
        >
          Add Person
        </Button>
      </div>

      {/* Filters Bar */}
      <Card className="p-4">
        <div className="flex flex-col sm:flex-row items-center gap-3">
          <div className="flex-1 w-full">
            <Input
              placeholder="Search by name or email..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              leftIcon={<Search className="w-4 h-4" />}
            />
          </div>

          <div className="flex items-center gap-2 w-full sm:w-auto">
            <Filter className="w-4 h-4 text-slate-400" />
            <Select value={roleFilter} onChange={(e) => setRoleFilter(e.target.value)} className="w-40">
              <option value="all">All Roles</option>
              <option value="coordinator">Coordinators</option>
              <option value="interviewer">Interviewers</option>
              <option value="candidate">Candidates</option>
            </Select>
          </div>
        </div>
      </Card>

      {/* Table */}
      {isLoading ? (
        <Spinner size="lg" label="Loading directory..." />
      ) : users.length === 0 ? (
        <EmptyState
          icon={Users}
          title="No users match your criteria"
          description="Try adjusting your search query or role filter, or add a new person to the directory."
          actionLabel="Add Person"
          onAction={() => {
            resetForm();
            setIsCreateModalOpen(true);
          }}
        />
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
              <TableHead>Email</TableHead>
              <TableHead>Role</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Profile / Attributes</TableHead>
              <TableHead className="text-right">Availability</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {users.map((u) => (
              <TableRow key={u.id}>
                <TableCell>
                  <div className="font-semibold text-slate-100">{u.name}</div>
                </TableCell>
                <TableCell>
                  <div className="flex items-center gap-1.5 text-xs text-slate-300 font-mono">
                    <Mail className="w-3.5 h-3.5 text-slate-500" />
                    <span>{u.email}</span>
                  </div>
                </TableCell>
                <TableCell>
                  <Badge variant={roleBadgeVariants[u.role]} size="sm">
                    {u.role}
                  </Badge>
                </TableCell>
                <TableCell>
                  <Badge variant={u.status === 'active' ? 'success' : 'danger'} size="sm">
                    {u.status}
                  </Badge>
                </TableCell>
                <TableCell>
                  {u.role === 'interviewer' && (
                    <div className="space-y-1">
                      <div className="flex items-center gap-2 text-xs text-slate-300">
                        <span className="text-slate-500">Cap:</span>
                        <span className="font-semibold">{u.capacity || 4}/day</span>
                        {u.department && (
                          <>
                            <span className="text-slate-600">•</span>
                            <span className="text-slate-400">{u.department}</span>
                          </>
                        )}
                      </div>
                      <div className="flex flex-wrap gap-1">
                        {(u.skills || []).map((skill) => (
                          <span
                            key={skill}
                            className="px-1.5 py-0.5 rounded text-[10px] bg-brand-500/10 text-brand-300 border border-brand-500/20 font-mono"
                          >
                            {skill}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  {u.role === 'candidate' && (
                    <div className="text-xs text-slate-300 space-y-0.5">
                      {u.roll_number && (
                        <div className="flex items-center gap-1 text-slate-400 font-mono">
                          <Hash className="w-3 h-3 text-slate-500" />
                          <span>{u.roll_number}</span>
                        </div>
                      )}
                      {u.branch && (
                        <div className="flex items-center gap-1 text-slate-400">
                          <BookOpen className="w-3 h-3 text-slate-500" />
                          <span>{u.branch}</span>
                        </div>
                      )}
                    </div>
                  )}

                  {u.role === 'coordinator' && (
                    <span className="text-xs text-slate-500 italic">Full administrator</span>
                  )}
                </TableCell>
                <TableCell className="text-right">
                  {u.role !== 'coordinator' && (
                    <Link to={`/coordinator/users/${u.id}/availability`}>
                      <Button variant="ghost" size="sm" leftIcon={<Clock className="w-3.5 h-3.5 text-brand-400" />}>
                        Edit
                      </Button>
                    </Link>
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}

      {/* Create User Modal */}
      <Modal
        isOpen={isCreateModalOpen}
        onClose={() => setIsCreateModalOpen(false)}
        title="Add New Person"
        description="Provision a coordinator, interviewer panelist, or student candidate"
        maxWidth="md"
      >
        <form onSubmit={handleSubmitCreate} className="space-y-4">
          <FormField label="Role Type" required>
            <Select value={formRole} onChange={(e) => setFormRole(e.target.value as UserRole)}>
              <option value="interviewer">Interviewer (Panelist)</option>
              <option value="candidate">Candidate (Student / Applicant)</option>
              <option value="coordinator">Coordinator (Staff / Admin)</option>
            </Select>
          </FormField>

          <FormField label="Full Name" required error={fieldErrors.name}>
            <Input
              value={formName}
              onChange={(e) => setFormName(e.target.value)}
              placeholder="e.g. Dr. Alan Turing"
              required
            />
          </FormField>

          <FormField label="Email Address" required error={fieldErrors.email}>
            <Input
              type="email"
              value={formEmail}
              onChange={(e) => setFormEmail(e.target.value)}
              placeholder="name@university.edu"
              required
            />
          </FormField>

          <FormField
            label="Temporary Password"
            required
            hint="Minimum 10 characters required"
            error={fieldErrors.password}
          >
            <Input
              type="password"
              value={formPassword}
              onChange={(e) => setFormPassword(e.target.value)}
              placeholder="••••••••••••"
              required
            />
          </FormField>

          {/* Interviewer fields */}
          {formRole === 'interviewer' && (
            <div className="p-4 rounded-xl bg-surface-elevated/80 border border-surface-border space-y-4">
              <h4 className="text-xs font-semibold text-slate-200 uppercase tracking-wider flex items-center gap-1.5">
                <Award className="w-4 h-4 text-emerald-400" />
                <span>Interviewer Configuration</span>
              </h4>

              <div className="grid grid-cols-2 gap-3">
                <FormField label="Daily Capacity" required error={fieldErrors.capacity}>
                  <Input
                    type="number"
                    min={1}
                    max={50}
                    value={formCapacity}
                    onChange={(e) => setFormCapacity(parseInt(e.target.value, 10))}
                    required
                  />
                </FormField>

                <FormField label="Department" error={fieldErrors.department}>
                  <Input
                    value={formDepartment}
                    onChange={(e) => setFormDepartment(e.target.value)}
                    placeholder="e.g. Engineering"
                  />
                </FormField>
              </div>

              <FormField label="Skills &amp; Domain Tags" hint="Press add or Enter to attach skill tags">
                <div className="flex gap-2">
                  <Input
                    value={skillInput}
                    onChange={(e) => setSkillInput(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') {
                        e.preventDefault();
                        handleAddSkill();
                      }
                    }}
                    placeholder="e.g. python, system_design"
                    leftIcon={<Tag className="w-3.5 h-3.5" />}
                  />
                  <Button type="button" variant="secondary" size="sm" onClick={handleAddSkill}>
                    <Plus className="w-4 h-4" />
                  </Button>
                </div>

                {formSkills.length > 0 && (
                  <div className="flex flex-wrap gap-1.5 mt-2">
                    {formSkills.map((s) => (
                      <span
                        key={s}
                        className="inline-flex items-center gap-1 px-2 py-1 rounded-md text-xs bg-brand-500/20 text-brand-300 border border-brand-500/30"
                      >
                        <span>{s}</span>
                        <button
                          type="button"
                          onClick={() => handleRemoveSkill(s)}
                          className="hover:text-rose-400"
                        >
                          <X className="w-3 h-3" />
                        </button>
                      </span>
                    ))}
                  </div>
                )}
              </FormField>
            </div>
          )}

          {/* Candidate fields */}
          {formRole === 'candidate' && (
            <div className="p-4 rounded-xl bg-surface-elevated/80 border border-surface-border space-y-4">
              <h4 className="text-xs font-semibold text-slate-200 uppercase tracking-wider flex items-center gap-1.5">
                <BookOpen className="w-4 h-4 text-sky-400" />
                <span>Candidate Profile</span>
              </h4>

              <div className="grid grid-cols-2 gap-3">
                <FormField label="Roll Number" error={fieldErrors.roll_number}>
                  <Input
                    value={formRollNumber}
                    onChange={(e) => setFormRollNumber(e.target.value)}
                    placeholder="e.g. CS-2026-042"
                  />
                </FormField>

                <FormField label="Branch / Specialization" error={fieldErrors.branch}>
                  <Input
                    value={formBranch}
                    onChange={(e) => setFormBranch(e.target.value)}
                    placeholder="e.g. Computer Science"
                  />
                </FormField>
              </div>
            </div>
          )}

          <div className="flex items-center justify-end gap-3 pt-3 border-t border-surface-border">
            <Button type="button" variant="outline" onClick={() => setIsCreateModalOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" variant="primary" isLoading={createUserMutation.isPending}>
              Create Person
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
};
